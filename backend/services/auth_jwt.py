from datetime import datetime, timedelta, timezone

import jwt

from config import get_settings
from models.schemas import Perfil


def create_token(sub: str, perfil: Perfil) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=s.jwt_expiration_hours)
    payload = {"sub": sub, "perfil": perfil, "iat": now, "exp": exp}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
