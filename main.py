from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.schemas.tool_envelope import ErroTool
from src.api.endpoints import (
    admin_auth,
    admin_finance,
    admin_inventory,
    admin_reservations,
    reservations,
    environments,
    availability,
    menu,
)

app = FastAPI(
    title="Giardini Reservations API",
    description="Backend API for managing reservations, environments, and time availability.",
    version="0.1.0",
)

origins = [
    "https://giardini.cafe",
    "https://www.giardini.cafe",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_auth.router)
app.include_router(admin_finance.router)
app.include_router(admin_inventory.router)
app.include_router(admin_reservations.router)
app.include_router(reservations.router)
app.include_router(environments.router)
app.include_router(availability.router)
app.include_router(menu.router)


# ---------------------------------------------------------------------------
# Envelope de erro das rotas de tool (docs/CONVENCAO_TOOLS.md §5)
#
# Vale só nos paths registrados como tool. As rotas antigas e as de escrita
# continuam com o {"detail": ...} do FastAPI, que o dashboard e o n8n já
# consomem -- é o caminho que a própria convenção descreve em §5.2.
# ---------------------------------------------------------------------------

_MENSAGEM_POR_STATUS = {
    400: ("PARAMETRO_INVALIDO", "Revise os parâmetros e chame de novo."),
    401: ("NAO_AUTORIZADO", "Confirme a chave de acesso configurada."),
    404: ("ENTIDADE_NAO_ENCONTRADA", "Confirme o nome com quem perguntou."),
    409: ("DADO_INDISPONIVEL", "Tente um período já fechado."),
}


@app.exception_handler(ErroTool)
async def erro_tool_handler(request: Request, exc: ErroTool):
    return JSONResponse(
        status_code=exc.status_code,
        content={"erro": {"codigo": exc.codigo, "mensagem": exc.mensagem,
                          "sugestao": exc.sugestao}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.method == "GET" and request.url.path in admin_inventory.TOOL_PATHS:
        codigo, sugestao = _MENSAGEM_POR_STATUS.get(
            exc.status_code, ("ERRO_INTERNO", None)
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"erro": {"codigo": codigo, "mensagem": str(exc.detail),
                              "sugestao": sugestao}},
        )

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
