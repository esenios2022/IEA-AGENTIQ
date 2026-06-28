"""Password hashing and session helpers for client accounts."""

import bcrypt
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from src.models import Client


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def get_current_client(request: Request, db: Session) -> Client:
    client_id = request.session.get("client_id")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    return client
