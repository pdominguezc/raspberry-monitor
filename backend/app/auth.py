from fastapi import Header, HTTPException, Query, status

from . import config


async def verify_token(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> None:
    """Acepta el token vía header 'Authorization: Bearer <token>' o query param ?token=
    (el query param es necesario para el WebSocket desde clientes que no pueden fijar headers,
    como algunas apps o el navegador al abrir el socket)."""
    supplied = None
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization.split(" ", 1)[1].strip()
    elif token:
        supplied = token

    if not supplied or supplied != config.API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o ausente")
