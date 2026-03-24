from fastapi import APIRouter, HTTPException, status
from passlib.context import CryptContext

from config import get_settings
from models.schemas import LoginRequest, LoginResponse, Perfil
from services.auth_jwt import create_token

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _resolve_perfil(email: str, senha: str) -> Perfil | None:
    s = get_settings()
    email_l = email.strip().lower()

    def check_vendedor() -> bool:
        if s.vendedor_email.strip().lower() != email_l:
            return False
        if s.allow_plain_passwords and s.vendedor_password and senha == s.vendedor_password:
            return True
        if s.vendedor_password_hash:
            return pwd_context.verify(senha, s.vendedor_password_hash)
        return False

    def check_prop() -> bool:
        if s.proprietaria_email.strip().lower() != email_l:
            return False
        if s.allow_plain_passwords and s.proprietaria_password and senha == s.proprietaria_password:
            return True
        if s.proprietaria_password_hash:
            return pwd_context.verify(senha, s.proprietaria_password_hash)
        return False

    if check_vendedor():
        return "vendedor"
    if check_prop():
        return "proprietaria"
    return None


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    perfil = _resolve_perfil(body.email, body.senha)
    if perfil is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha inválidos")
    token = create_token(body.email.strip().lower(), perfil)
    return LoginResponse(token=token, perfil=perfil)
