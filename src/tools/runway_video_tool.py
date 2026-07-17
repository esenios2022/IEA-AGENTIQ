"""
RunwayVideoTool — 2026-07-17. Primera herramienta real de generación de
video de la Biblioteca Inteligente de Marketing: genera un clip corto con
la API de Runway (modelo veo3.1, text-to-video) a partir de un prompt,
sube el binario real a storage S3-compatible y deja el resultado en la
Biblioteca como borrador — mismo patrón que GeminiImageTool (nunca se
auto-aprueba lo que un agente genera).

Confirmado real ese mismo día contra la API (cuenta con credito real
cargado): la generación es asincrona -- POST /v1/text_to_video devuelve
un task id, hay que hacer polling a GET /v1/tasks/{id} hasta que
status sea SUCCEEDED (o FAILED), y el resultado final es una URL firmada
(expira) al mp4 -- por eso esta tool descarga el archivo enseguida en vez
de guardar la URL directamente.

veo3.1 solo acepta duration en bloques de 4, 6 u 8 segundos (confirmado
real via el error de validación de la API) -- un Reel de 30s con guion de
5 escenas encaja natural en 5 clips de 6s.
"""

import time
import uuid

import requests
from crewai.tools import BaseTool

from src import library, library_storage
from src.config import settings
from src.cost import get_daily_spend, record_usage
from src.database import SessionLocal
from src.llm_pricing import calculate_cost_usd
from src.models import Agent

RUNWAY_API_BASE = "https://api.dev.runwayml.com/v1"
RUNWAY_API_VERSION = "2024-11-06"
RUNWAY_MODEL = "veo3.1"
VALID_DURATIONS = (4, 6, 8)
VALID_RATIOS = ("1280:720", "720:1280", "1080:1920", "1920:1080")
POLL_INTERVAL_SECONDS = 10
POLL_TIMEOUT_SECONDS = 300
FORCED_STATUS = "borrador"
DEFAULT_CATEGORY = "Videos"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.runway_api_key}",
        "X-Runway-Version": RUNWAY_API_VERSION,
        "Content-Type": "application/json",
    }


class RunwayVideoTool(BaseTool):
    name: str = "runway_api"
    description: str = (
        "Genera un clip de video real con IA (Runway, modelo veo3.1) a partir de una descripción de "
        "escena en texto, y lo guarda en la Biblioteca Inteligente de Marketing. Usala para b-roll "
        "cinematico (no avatares hablando -- para eso existe otra herramienta). Duracion solo puede "
        "ser 4, 6 u 8 segundos. El resultado SIEMPRE queda en estado 'borrador' -- un humano tiene que "
        "revisarlo antes de que otro agente pueda reutilizarlo. Puede tardar unos minutos en generarse."
    )
    client_id: str | None = None
    created_by_agent_id: str | None = None

    def _run(
        self,
        prompt: str,
        title: str,
        duration: int = 6,
        ratio: str = "720:1280",
        subcategory: str | None = None,
        description: str | None = None,
    ) -> str:
        if not settings.runway_api_key:
            return "Error: RUNWAY_API_KEY no está configurada en la plataforma — no se puede generar el video."
        if duration not in VALID_DURATIONS:
            return f"Error: duration inválida ({duration}). Runway solo acepta {VALID_DURATIONS} segundos."
        if ratio not in VALID_RATIOS:
            return f"Error: ratio inválido ({ratio}). Valores posibles: {VALID_RATIOS}."

        # 2026-07-17 -- check_budget() (src/cost.py) solo corre una vez al
        # INICIO de la corrida del agente, no antes de cada llamada a una
        # tool paga dentro de esa misma corrida -- confirmado real: nada
        # frenaba a un agente de encadenar N generaciones de video (~$1.60c/u
        # a esta duracion) muy por encima de su daily_budget_usd en una sola
        # corrida. Este chequeo cierra ese hueco a nivel de la tool misma,
        # antes de gastar un solo credito real.
        if self.created_by_agent_id:
            guard_db = SessionLocal()
            try:
                agent = guard_db.query(Agent).filter(Agent.id == self.created_by_agent_id).first()
                if agent is not None and agent.daily_budget_usd and agent.daily_budget_usd > 0:
                    spent_today = get_daily_spend(guard_db, agent.id)
                    estimated_cost = calculate_cost_usd("runway-veo3.1", 0, duration)
                    if spent_today + estimated_cost > agent.daily_budget_usd:
                        return (
                            f"Error: generar este video (~${estimated_cost:.2f}) superaria el presupuesto diario "
                            f"de este agente (${agent.daily_budget_usd:.2f}, ya gastado hoy: ${spent_today:.2f}). "
                            "No se genero nada, no se gasto ningun credito real."
                        )
            finally:
                guard_db.close()

        create_resp = requests.post(
            f"{RUNWAY_API_BASE}/text_to_video",
            headers=_headers(),
            json={"model": RUNWAY_MODEL, "promptText": prompt, "ratio": ratio, "duration": duration},
            timeout=30,
        )
        if create_resp.status_code != 200:
            return f"Error creando la tarea en Runway ({create_resp.status_code}): {create_resp.text[:300]}"

        task_id = create_resp.json().get("id")
        if not task_id:
            return f"Error: Runway no devolvió un task id. Respuesta: {create_resp.text[:300]}"

        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        video_url: str | None = None
        while time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_SECONDS)
            status_resp = requests.get(f"{RUNWAY_API_BASE}/tasks/{task_id}", headers=_headers(), timeout=30)
            if status_resp.status_code != 200:
                return f"Error consultando el estado de la tarea ({status_resp.status_code}): {status_resp.text[:300]}"
            data = status_resp.json()
            status = data.get("status")
            if status == "SUCCEEDED":
                output = data.get("output") or []
                video_url = output[0] if output else None
                break
            if status == "FAILED":
                return f"Error: la generación falló del lado de Runway. Detalle: {data}"
        else:
            return f"Error: la generación de Runway no terminó en {POLL_TIMEOUT_SECONDS}s (task_id={task_id})."

        if not video_url:
            return f"Error: la tarea terminó SUCCEEDED pero sin URL de salida. task_id={task_id}."

        video_resp = requests.get(video_url, timeout=60)
        if video_resp.status_code != 200:
            return f"Error descargando el video generado ({video_resp.status_code})."
        video_bytes = video_resp.content

        filename = f"{uuid.uuid4()}.mp4"
        storage_key = library_storage.build_storage_key(self.client_id, DEFAULT_CATEGORY, subcategory, filename)

        try:
            library_storage.upload_asset(video_bytes, storage_key, content_type="video/mp4")
        except library_storage.LibraryStorageNotConfiguredError:
            return (
                "Error: el almacenamiento S3-compatible de la Biblioteca no está configurado — "
                "el video se generó pero no se pudo guardar. Avisá al admin."
            )
        except library_storage.LibraryStorageError as exc:
            return f"Error subiendo el video al almacenamiento: {exc}"

        db = SessionLocal()
        try:
            asset = library.create_asset(
                db,
                client_id=self.client_id,
                category=DEFAULT_CATEGORY,
                subcategory=subcategory,
                title=title,
                description=description,
                file_type="video",
                mime_type="video/mp4",
                file_extension="mp4",
                file_size_bytes=len(video_bytes),
                storage_key=storage_key,
                text_content=prompt,
                created_by_agent_id=self.created_by_agent_id,
                status=FORCED_STATUS,
            )
            asset_id = asset.id

            if self.created_by_agent_id:
                record_usage(
                    db,
                    agent_id=self.created_by_agent_id,
                    client_id=self.client_id,
                    execution_id=None,
                    model="runway-veo3.1",
                    tier="runway-platform",
                    provider="runway",
                    input_tokens=0,
                    output_tokens=duration,
                    success=True,
                    input_text=prompt,
                    platform_cost=True,
                    content_asset_id=asset_id,
                )
        finally:
            db.close()

        url = library_storage.get_asset_url(storage_key)
        return f"Video generado ({duration}s) y guardado en la Biblioteca como borrador. asset_id={asset_id}, url={url}."
