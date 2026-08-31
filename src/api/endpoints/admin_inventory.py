"""Domínio de estoque.

As cinco rotas de LEITURA são tools da Júlia e seguem docs/CONVENCAO_TOOLS.md:
`GET`, envelope de quatro chaves, `limite`, entidade por nome, teto de 50 linhas.

As quatro de ESCRITA não são tools — a convenção cobre só leitura. Elas seguem o
padrão administrativo do `PATCH /admin/reservations/{id}/status` e nunca entram
na lista de ferramentas.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.dependencies.admin_auth import validate_admin_or_internal
from src.api.dependencies.date_range import DateRange, date_range_canonico
from src.db.session import get_db
from src.schemas.admin_inventory import (
    CompraEntrada,
    CompraResposta,
    ConsumoEntrada,
    ConsumoResposta,
    ContagemEntrada,
    ContagemResposta,
    DeteccaoQrResposta,
    FotoCupomEntrada,
    ImportarInsumosEntrada,
    NotaLidaResposta,
    ImportarInsumosResposta,
    MapearItemEntrada,
    MapearItemResposta,
    PerdaEntrada,
    PerdaResposta,
)
from src.schemas.tool_envelope import RespostaTool
from src.services import nfce_foto_service, sefaz_nfce_service
from src.services.admin_inventory_service import AdminInventoryService
from src.services.admin_inventory_write_service import AdminInventoryWriteService

router = APIRouter(prefix="/admin/inventory", tags=["Admin Inventory"])

# Paths que o handler de erro de main.py converte para o envelope {"erro": {...}}.
# Só leitura: as rotas de escrita continuam no {"detail": ...} do FastAPI.
TOOL_PATHS = frozenset({
    "/admin/inventory/saldo",
    "/admin/inventory/criticos",
    "/admin/inventory/precos",
    "/admin/inventory/cmv",
    "/admin/inventory/compras",
})


# ============================================================================
# LEITURA — tools
# ============================================================================

@router.get(
    "/saldo",
    response_model=RespostaTool,
    summary="Saldo de estoque por insumo",
    description=(
        "Saldo atual de cada insumo, com a unidade, o mínimo configurado e por "
        "quantos dias o saldo cobre o consumo médio. Use para 'quanto tem de X?', "
        "'como está o estoque?'. Para saber só o que está acabando, use "
        "estoque_itens_criticos."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def saldo(
    insumo: str | None = Query(default=None, description="Nome ou código do insumo."),
    categoria: str | None = Query(default=None, description="Categoria do insumo."),
    limite: int = Query(default=15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return AdminInventoryService(db).saldo(insumo, categoria, limite)


@router.get(
    "/criticos",
    response_model=RespostaTool,
    summary="Insumos abaixo do mínimo",
    description=(
        "Insumos abaixo do nível mínimo, do mais crítico para o menos, com saldo, "
        "mínimo e cobertura em dias. Use para 'o que está acabando?', 'preciso "
        "comprar o quê?'. Responde em quantidade, não em reais."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def criticos(
    categoria: str | None = Query(default=None, description="Categoria do insumo."),
    limite: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return AdminInventoryService(db).criticos(categoria, limite)


@router.get(
    "/precos",
    response_model=RespostaTool,
    summary="Histórico de preço de um insumo",
    description=(
        "Quanto cada compra de um insumo custou por unidade base, por fornecedor e "
        "por data, com preço médio, mínimo, máximo e a variação já calculada. Use "
        "para 'o café subiu?', 'quanto pago no leite?', 'qual fornecedor está mais "
        "barato?'."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def precos(
    insumo: str = Query(description="Nome ou código do insumo. Obrigatório."),
    fornecedor: str | None = Query(default=None, description="Nome do fornecedor."),
    limite: int = Query(default=10, ge=1, le=50),
    intervalo: DateRange = Depends(date_range_canonico),
    db: Session = Depends(get_db),
):
    intervalo = intervalo.require_both_or_none()
    return AdminInventoryService(db).historico_preco(
        insumo, fornecedor, intervalo.start_date, intervalo.end_date, limite
    )


@router.get(
    "/cmv",
    response_model=RespostaTool,
    summary="CMV do período",
    description=(
        "Custo da mercadoria vendida no período, por custo médio ponderado, com o "
        "percentual sobre a receita e a quebra por insumo. Use para 'qual o CMV do "
        "mês?', 'quanto custou o que a gente vendeu?'. Não use para saber quanto se "
        "gastou em compras — para isso use estoque_compras."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def cmv(
    limite: int = Query(default=10, ge=1, le=50),
    intervalo: DateRange = Depends(date_range_canonico),
    db: Session = Depends(get_db),
):
    start_date, end_date = intervalo.require_both()
    return AdminInventoryService(db).cmv(start_date, end_date, limite)


@router.get(
    "/compras",
    response_model=RespostaTool,
    summary="Compras do período",
    description=(
        "Compras registradas no período, com fornecedor, valor, número de itens e "
        "quantos ainda precisam de mapeamento. Use para 'quanto comprei esse mês?', "
        "'quais notas entraram?', 'tem nota pendente de revisão?'."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def compras(
    fornecedor: str | None = Query(default=None, description="Nome do fornecedor."),
    status: str | None = Query(default=None, description="Status da compra."),
    limite: int = Query(default=15, ge=1, le=50),
    intervalo: DateRange = Depends(date_range_canonico),
    db: Session = Depends(get_db),
):
    intervalo = intervalo.require_both_or_none()
    return AdminInventoryService(db).compras(
        intervalo.start_date, intervalo.end_date, fornecedor, status, limite
    )


# ============================================================================
# ESCRITA — rota administrativa, não é tool
# ============================================================================

@router.post(
    "/compras",
    response_model=CompraResposta,
    status_code=201,
    summary="Registrar compra a partir dos itens da nota",
    description=(
        "Uma transação: os N itens entram juntos ou nenhum entra. Item sem "
        "mapeamento confirmado não aborta a compra — entra como "
        "'precisa_mapeamento' e não gera movimento de estoque. Idempotente pela "
        "chave da NFC-e. Por padrão vincula ou cria a despesa correspondente no "
        "financeiro; use `criar_despesa: false` quando o dinheiro já estiver "
        "lançado por outro caminho, como na carga de estoque inicial."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def registrar_compra(entrada: CompraEntrada, db: Session = Depends(get_db)):
    return AdminInventoryWriteService(db).registrar_compra(entrada)


@router.post(
    "/compras/{compra_id}/itens/{item_id}/mapear",
    response_model=MapearItemResposta,
    summary="Confirmar o mapeamento de um item da nota",
    description=(
        "Cria o mapeamento como confirmado, fecha a versão anterior, aplica ao item "
        "e gera o movimento de entrada — tudo numa transação. É o único caminho "
        "pelo qual uma conversão de unidade passa a valer: IA nunca decide isso."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def mapear_item(
    compra_id: uuid.UUID,
    item_id: uuid.UUID,
    entrada: MapearItemEntrada,
    db: Session = Depends(get_db),
):
    return AdminInventoryWriteService(db).mapear_item(compra_id, item_id, entrada)


@router.post(
    "/insumos",
    response_model=ImportarInsumosResposta,
    status_code=201,
    summary="Importar a aba de insumos da planilha",
    description=(
        "Carga em lote do catálogo, com upsert por `codigo`, numa transação só. "
        "Reimportar a mesma planilha é inofensivo. Trocar a `unidade_base` de um "
        "insumo que já tem movimento é recusado com 409: invalidaria o saldo."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def importar_insumos(entrada: ImportarInsumosEntrada, db: Session = Depends(get_db)):
    return AdminInventoryWriteService(db).importar_insumos(entrada)


@router.post(
    "/consumos",
    response_model=ConsumoResposta,
    status_code=201,
    summary="Aplicar a ficha técnica sobre as vendas do dia",
    description=(
        "Recebe as vendas de um dia por `eye_product_id` e gera as saídas de "
        "estoque pela ficha técnica vigente, com o custo médio ponderado do "
        "momento. Produto sem ficha não gera saída e volta em `nao_cobertos`. "
        "Idempotente por dia, produto e insumo."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def registrar_consumo(entrada: ConsumoEntrada, db: Session = Depends(get_db)):
    return AdminInventoryWriteService(db).registrar_consumo(entrada)


@router.post(
    "/contagens",
    response_model=ContagemResposta,
    status_code=201,
    summary="Registrar contagem de inventário",
    description=(
        "Com `fechar=true`, tira o snapshot do saldo de sistema e gera um "
        "ajuste_contagem por item com diferença. Idempotente pela "
        "`chave_idempotencia` enviada."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def registrar_contagem(entrada: ContagemEntrada, db: Session = Depends(get_db)):
    return AdminInventoryWriteService(db).registrar_contagem(entrada)


@router.post(
    "/perdas",
    response_model=PerdaResposta,
    status_code=201,
    summary="Lançar perda de insumo",
    description=(
        "Gera um movimento de saída com o custo médio ponderado do momento. "
        "Idempotente pela `chave_idempotencia` enviada."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def lancar_perda(entrada: PerdaEntrada, db: Session = Depends(get_db)):
    return AdminInventoryWriteService(db).lancar_perda(entrada)


@router.post(
    "/nfce/detecta",
    response_model=DeteccaoQrResposta,
    summary="Ler o QR de um cupom fotografado",
    description=(
        "Diz se a foto tem um QR e se ele é de NFC-e, devolvendo a chave de 44 "
        "dígitos e a URL de consulta. Não fala com a SEFAZ: é a checagem barata "
        "que a classificação de anexo usa para decidir se a foto é nota fiscal "
        "ou comprovante de pagamento. A foto passa por algumas correções "
        "(cinza, ampliação, contraste, binarização) antes de a leitura desistir."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def detecta_qr_nfce(entrada: FotoCupomEntrada):
    try:
        return nfce_foto_service.detecta(entrada.imagem_base64)
    except nfce_foto_service.ImagemInvalida as erro:
        raise HTTPException(status_code=422, detail=str(erro))


@router.post(
    "/nfce/foto",
    response_model=NotaLidaResposta,
    summary="Ler a nota inteira a partir da foto do cupom",
    description=(
        "Lê o QR da foto, consulta a NFC-e na SEFAZ e devolve a nota "
        "estruturada, na mesma forma que a leitura do PDF produz — o fluxo a "
        "jusante não sabe de onde a nota veio. A conferência aritmética vale "
        "igual: item a item e na soma contra o total declarado. Fonte oficial "
        "não dispensa a conta, porque o que pode quebrar é a leitura."
    ),
    dependencies=[Depends(validate_admin_or_internal)],
)
def le_nfce_da_foto(entrada: FotoCupomEntrada):
    try:
        deteccao = nfce_foto_service.detecta(entrada.imagem_base64)
    except nfce_foto_service.ImagemInvalida as erro:
        raise HTTPException(status_code=422, detail=str(erro))

    if not deteccao["tem_qr"]:
        return _nao_leu("sem_qr", "não achei nenhum QR code nessa foto")

    if not deteccao["e_nfce"]:
        return _nao_leu(
            "nao_e_nfce",
            "o QR dessa foto não é de nota fiscal",
            url_consulta=deteccao["url_consulta"],
        )

    try:
        return sefaz_nfce_service.le_nota(deteccao["conteudo_qr"])
    except sefaz_nfce_service.ConsultaInvalida as erro:
        return _nao_leu("nao_e_nfce", str(erro),
                        chave_nfe=deteccao["chave_nfe"],
                        url_consulta=deteccao["url_consulta"])
    except sefaz_nfce_service.SefazIndisponivel as erro:
        # Falha passageira: a chave está lida e a nota existe. Não é caso de
        # pedir foto melhor, é caso de tentar de novo.
        return _nao_leu("sefaz_indisponivel", str(erro),
                        chave_nfe=deteccao["chave_nfe"],
                        url_consulta=deteccao["url_consulta"])


def _nao_leu(motivo: str, problema: str, **extras) -> dict:
    return {"conferido": False, "motivo": motivo, "problemas": [problema],
            "avisos": [], "itens": [], "total_itens": 0, **extras}
