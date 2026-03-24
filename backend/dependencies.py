from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from models.schemas import Perfil
from services.auth_jwt import decode_token

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        return {"sub": payload["sub"], "perfil": payload["perfil"]}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_vendedor(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if user["perfil"] != "vendedor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso de vendedor necessário")
    return user


def require_proprietaria(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if user["perfil"] != "proprietaria":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso de proprietária necessário"
        )
    return user


def require_perfil(*perfis: Perfil):
    def _inner(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if user["perfil"] not in perfis:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil não autorizado")
        return user

    return _inner
