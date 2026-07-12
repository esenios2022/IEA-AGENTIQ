"""
FASE 2.2 — el primer ciclo real de automatización comercial, orientado
a la adquisición de PACIENTES para eAlumina (no seguimiento de leads
genéricos — aclaración explícita del Arquitecto Principal durante esta
misma fase).

Lead nuevo -> analisis/clasificacion IA -> generacion del mensaje ->
envio por WhatsApp -> registro de interaccion -> actualizacion del
estado del Lead.

Regla arquitectonica seguida literalmente: IEA-AGENTIQ no ejecuta IA
por su cuenta para este flujo — `ai_lab_client.generate_message()`
corre un RUN_AGENT real dentro del AI LAB (AIRuntime real), y
`ai_lab_client.whatsapp_send()` entrega el mensaje via el
WhatsAppGateway real del AI LAB (Evolution API, Sprint 21/26). Este
modulo solo orquesta: nunca llama a Anthropic/OpenAI/Evolution
directamente.

Nunca deja escapar una excepcion hacia el llamador (mismo patron de
resiliencia que el resto de este repositorio — ver
`src/tool_assembly.py::_composio_tools`, `src/tools/web_search.py`):
un fallo de red hacia el AI LAB no debe romper la creacion de un Lead.
El fallo SI queda registrado como un `LeadInteraction` con
`status="failed"`, visible en /admin/leads.

Lo que este modulo deliberadamente NO hace (preparado, no implementado
— ver docs/AI_LAB_INTEGRATION.md): seleccionar un terapeuta real. Ese
paso necesita un directorio real de terapeutas (idioma/especialidad/
disponibilidad/modalidad), que hoy vive en eAlumina — un repositorio
al que este agente todavia no tiene acceso. Los campos nuevos en
`Lead` (idioma, tipo_terapia, disponibilidad, clasificacion_ia)
existen para que ese paso futuro tenga con que trabajar sin volver a
tocar el modelo de datos.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.ai_lab_client import AiLabNotConfiguredError, AiLabRequestError, ai_lab_client
from src.models import Lead, LeadInteraction

CLASSIFICATION_PROMPT_TEMPLATE = (
    "Sos un asistente clinico-administrativo de eAlumina, una plataforma de salud mental "
    "que conecta pacientes con terapeutas. Analiza este paciente potencial y respondé en UNA "
    "sola linea, en español, con el formato 'tipo_terapia: <categoria breve> | urgencia: <baja/media/alta>'. "
    "No agregues nada mas.\n\n"
    "Nombre: {nombre}\n"
    "Interes/necesidad declarada: {plan_interes}\n"
    "Tipo de terapia ya indicado (si lo hay): {tipo_terapia}\n"
    "Notas: {notas}\n"
    "Pais/ciudad: {pais}/{ciudad}\n"
    "Idioma: {idioma}"
)

WELCOME_PROMPT_TEMPLATE = (
    "Sos un asistente comercial de eAlumina, una plataforma de salud mental que conecta "
    "pacientes con terapeutas. Escribi un mensaje breve de bienvenida por WhatsApp (maximo "
    "3 frases, en el idioma '{idioma}', calido y profesional, sin emojis excesivos) para un "
    "paciente potencial llamado {nombre}. Necesidad declarada: {plan_interes}. "
    "Clasificacion clinica preliminar: {clasificacion_ia}. "
    "El mensaje debe confirmar que recibimos su consulta y que un especialista lo va a contactar pronto "
    "para coordinar disponibilidad ({disponibilidad})."
)


def _classification_prompt(lead: Lead) -> str:
    return CLASSIFICATION_PROMPT_TEMPLATE.format(
        nombre=lead.nombre,
        plan_interes=lead.plan_interes or "no especificado",
        tipo_terapia=lead.tipo_terapia or "no especificado",
        notas=lead.notas or "sin notas",
        pais=lead.pais or "no especificado",
        ciudad=lead.ciudad or "no especificado",
        idioma=lead.idioma,
    )


def _welcome_prompt(lead: Lead) -> str:
    return WELCOME_PROMPT_TEMPLATE.format(
        idioma=lead.idioma,
        nombre=lead.nombre,
        plan_interes=lead.plan_interes or "no especificado",
        clasificacion_ia=lead.clasificacion_ia or "pendiente de clasificar",
        disponibilidad=lead.disponibilidad or "a coordinar",
    )


def _log_failure(lead: Lead, db: Session, exc: Exception) -> LeadInteraction:
    interaction = LeadInteraction(lead_id=lead.id, channel="whatsapp", direction="outbound", message="", status="failed", error=str(exc))
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    print(f"[lead_qualification] lead {lead.id} contact failed: {exc}", flush=True)
    return interaction


def qualify_and_contact_lead(lead: Lead, db: Session) -> LeadInteraction | None:
    """
    Ejecuta el ciclo completo para UN lead/paciente potencial ya
    persistido (con id real). Retorna el LeadInteraction registrado, o
    None si el lead no tiene telefono (nada que contactar por este
    canal todavia — no es un error, ver docs/AI_LAB_INTEGRATION.md
    sobre canales adicionales futuros).

    `lead.tenant` decide contra que tenant del AI LAB se ejecuta —
    "ealumina" hoy, pero el mismo codigo sirve para Terra Araras u
    otro cliente de IEA AGENTIQ sin cambios, solo cambiando ese campo.
    """
    if not lead.telefono:
        return None

    tenant_id = lead.tenant
    conversation_id = f"lead-{lead.id}"

    try:
        # Paso 1: analisis/clasificacion real — deliberadamente separado del
        # mensaje de bienvenida (dos llamadas reales al AI LAB, no una sola
        # mezclando ambas responsabilidades).
        if not lead.clasificacion_ia:
            lead.clasificacion_ia = ai_lab_client.generate_message(tenant_id=tenant_id, prompt=_classification_prompt(lead))
            db.commit()

        # Paso 2: mensaje de bienvenida real, ya informado por la clasificacion.
        message = ai_lab_client.generate_message(tenant_id=tenant_id, prompt=_welcome_prompt(lead))
        ai_lab_client.whatsapp_send(tenant_id=tenant_id, conversation_id=conversation_id, to=lead.telefono, text=message)
    except (AiLabNotConfiguredError, AiLabRequestError) as exc:
        return _log_failure(lead, db, exc)

    interaction = LeadInteraction(lead_id=lead.id, channel="whatsapp", direction="outbound", message=message, status="sent")
    db.add(interaction)
    lead.estado = "contactado"
    db.commit()
    db.refresh(interaction)
    print(f"[lead_qualification] lead {lead.id} contacted successfully, estado -> contactado", flush=True)
    return interaction
