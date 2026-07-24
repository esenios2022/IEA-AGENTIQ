"""Responde en publico + manda el link real por DM privado cuando alguien
comenta la palabra clave en un post de Instagram.

Nota real (2026-07-24): la conexion de Instagram usa la App de Meta que
administra Composio (`is_composio_managed=True`), no una App propia — y
Composio no tiene ningun trigger/webhook de Instagram entre sus 367 tipos
disponibles (verificado con `composio.triggers.list_enum()`). Por eso esto
funciona por POLLING (consultar los comentarios nuevos cada cierto
intervalo via `scheduler.py`) en vez de por webhook entrante. Si algun dia
tenemos una App de Meta propia, `process_webhook_payload` ya queda lista
para ese camino sin tocar la logica de matching/respuesta.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.config import settings
from src.connectors.providers.base import SocialProviderError
from src.connectors.registry import CONNECTORS
from src.database import SessionLocal
from src.models import InstagramWebhookEvent

COMPOSIO_USER_ID = "ealumina"

DEFAULT_INSTAGRAM_DM_TEXT = (
    "Oi! Aqui está o link do nosso grupo oficial do WhatsApp — é por lá que "
    "você recebe o link da sala do evento de lançamento da EALumina, 25 de "
    "julho às 18h: https://chat.whatsapp.com/IxNvSPBAqhF0FVKVqS8Jtb"
)


def process_comment_event(
    db: Session, comment_id: str, text_raw: str, media_id: str | None, username: str | None
) -> InstagramWebhookEvent | None:
    """Procesa un comentario real: si ya se proceso (dedup) no hace nada y
    devuelve None. Si coincide la palabra clave, responde en publico y manda
    el DM privado real. Siempre persiste el intento (matched_keyword=True)
    para no reprocesarlo en la proxima vuelta del poll."""
    already = db.query(InstagramWebhookEvent).filter(InstagramWebhookEvent.comment_id == comment_id).first()
    if already is not None:
        return None

    keyword = settings.instagram_dm_trigger_keyword.strip().lower()
    matched = keyword in (text_raw or "").lower()
    event = InstagramWebhookEvent(
        comment_id=comment_id, media_id=media_id, commenter_username=username, matched_keyword=matched,
    )
    if not matched:
        db.add(event)
        db.commit()
        return event

    provider = CONNECTORS["instagram"].provider
    error_parts: list[str] = []

    try:
        provider.proxy(
            COMPOSIO_USER_ID, "instagram", f"/{comment_id}/replies", "POST",
            body={"message": settings.instagram_comment_reply_text},
        )
        event.public_reply_sent = True
    except SocialProviderError as exc:
        error_parts.append(f"reply publica: {exc}")

    try:
        ig_user_id = provider.call_action(COMPOSIO_USER_ID, "INSTAGRAM_GET_USER_INFO", {}).get("id")
        dm_text = settings.instagram_dm_reply_text or DEFAULT_INSTAGRAM_DM_TEXT
        provider.proxy(
            COMPOSIO_USER_ID, "instagram", f"/{ig_user_id}/messages", "POST",
            body={"recipient": {"comment_id": comment_id}, "message": {"text": dm_text}},
        )
        event.dm_sent = True
    except SocialProviderError as exc:
        error_parts.append(f"DM privado: {exc}")

    if error_parts:
        event.error = " | ".join(error_parts)
    print(
        f"[instagram_comment_automation] comment {comment_id} de @{username}: "
        f"reply_publica={event.public_reply_sent} dm={event.dm_sent} error={event.error}",
        flush=True,
    )
    db.add(event)
    db.commit()
    return event


def process_webhook_payload(payload: dict) -> None:
    """Camino para cuando tengamos una App de Meta propia con webhook real
    entrante — no se usa hoy (ver docstring del modulo), pero la logica de
    matching/respuesta es la misma que el polling."""
    db = SessionLocal()
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "comments":
                    continue
                value = change.get("value") or {}
                comment_id = value.get("id")
                if not comment_id:
                    continue
                process_comment_event(
                    db,
                    comment_id=comment_id,
                    text_raw=value.get("text") or "",
                    media_id=(value.get("media") or {}).get("id"),
                    username=(value.get("from") or {}).get("username"),
                )
    finally:
        db.close()


def poll_recent_comments(lookback_media: int = 5) -> None:
    """Job real de polling (ver scheduler.py): revisa los comentarios de los
    ultimos `lookback_media` posts y procesa los que sean nuevos."""
    provider = CONNECTORS["instagram"].provider
    db = SessionLocal()
    try:
        info = provider.call_action(COMPOSIO_USER_ID, "INSTAGRAM_GET_USER_INFO", {})
        ig_user_id = info.get("id")
        if not ig_user_id:
            return
        media = provider.call_action(
            COMPOSIO_USER_ID, "INSTAGRAM_GET_IG_USER_MEDIA", {"ig_user_id": ig_user_id, "limit": lookback_media},
        )
        for post in media.get("data", []):
            media_id = post.get("id")
            if not media_id:
                continue
            try:
                comments = provider.call_action(COMPOSIO_USER_ID, "INSTAGRAM_GET_POST_COMMENTS", {"ig_post_id": media_id})
            except SocialProviderError as exc:
                print(f"[instagram_comment_automation] no se pudieron leer comentarios de {media_id}: {exc}", flush=True)
                continue
            for comment in comments.get("data", []):
                comment_id = comment.get("id")
                if not comment_id:
                    continue
                from_user = comment.get("from") or {}
                process_comment_event(
                    db,
                    comment_id=comment_id,
                    text_raw=comment.get("text") or "",
                    media_id=media_id,
                    username=from_user.get("username"),
                )
    finally:
        db.close()
