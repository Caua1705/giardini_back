import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from src.models import (
    Document,
    Expense,
    Purchase,
    PurchaseItem,
    StockCount,
    StockCountItem,
    StockMovement,
    Supplier,
    SupplierMapping,
    Supply,
)

# A extensao `unaccent` nao esta instalada neste banco. Para casar nome de
# entidade sem depender de acento, tira-se o acento com translate(), que e
# deterministico e nao precisa de extensao nenhuma.
_COM_ACENTO = "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ"
_SEM_ACENTO = "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC"


def _normaliza(coluna):
    return func.translate(func.lower(func.btrim(coluna)), _COM_ACENTO, _SEM_ACENTO)


def _normaliza_texto(valor: str) -> str:
    tabela = str.maketrans(_COM_ACENTO, _SEM_ACENTO)
    return valor.strip().lower().translate(tabela)


class InventoryRepository:
    """Consultas do dominio de estoque.

    Leitura agrega no banco e devolve numero pronto -- a rota de tool nao pode
    receber numerador e denominador esperando divisao (CONVENCAO_TOOLS.md 3.2).
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ apoio

    def buscar_insumo_por_nome_ou_codigo(self, termo: str) -> Supply | None:
        alvo = _normaliza_texto(termo)
        return (
            self.db.query(Supply)
            .filter(
                or_(
                    _normaliza(Supply.codigo) == alvo,
                    _normaliza(Supply.nome) == alvo,
                )
            )
            .first()
        )

    def listar_nomes_de_insumo(self, limite: int = 20) -> list[str]:
        """Para a mensagem de ENTIDADE_NAO_ENCONTRADA listar as opcoes validas."""
        linhas = (
            self.db.query(Supply.nome)
            .filter(Supply.ativo.is_(True))
            .order_by(Supply.nome)
            .limit(limite)
            .all()
        )
        return [linha[0] for linha in linhas]

    def listar_categorias(self) -> list[str]:
        linhas = (
            self.db.query(Supply.categoria)
            .filter(Supply.ativo.is_(True), Supply.categoria.isnot(None))
            .distinct()
            .order_by(Supply.categoria)
            .all()
        )
        return [linha[0] for linha in linhas]

    def buscar_fornecedor_por_nome(self, termo: str) -> Supplier | None:
        alvo = _normaliza_texto(termo)
        return (
            self.db.query(Supplier)
            .filter(
                or_(
                    _normaliza(Supplier.razao_social) == alvo,
                    _normaliza(Supplier.nome_fantasia) == alvo,
                )
            )
            .first()
        )

    def listar_nomes_de_fornecedor(self, limite: int = 20) -> list[str]:
        linhas = (
            self.db.query(Supplier.razao_social)
            .filter(Supplier.ativo.is_(True))
            .order_by(Supplier.razao_social)
            .limit(limite)
            .all()
        )
        return [linha[0] for linha in linhas]

    # ------------------------------------------------------------ 1 e 2: saldo

    def _base_saldo(self, so_criticos: bool, janela_dias: int, hoje: date):
        """Saldo, consumo medio e cobertura por insumo, tudo agregado no banco."""
        desde = hoje - timedelta(days=janela_dias)

        saldo = func.coalesce(func.sum(StockMovement.quantidade_base), 0)
        consumo = func.coalesce(
            func.sum(
                func.abs(StockMovement.quantidade_base)
            ).filter(
                and_(
                    StockMovement.tipo == "consumo",
                    StockMovement.ocorreu_em >= desde,
                )
            ),
            0,
        )
        ultima_compra = func.max(StockMovement.ocorreu_em).filter(
            StockMovement.tipo == "compra"
        )

        consulta = (
            self.db.query(
                Supply.id.label("insumo_id"),
                Supply.codigo,
                Supply.nome,
                Supply.categoria,
                Supply.unidade_base,
                Supply.estoque_minimo,
                saldo.label("saldo"),
                consumo.label("consumo_janela"),
                ultima_compra.label("ultima_compra"),
            )
            .outerjoin(StockMovement, StockMovement.insumo_id == Supply.id)
            .filter(Supply.ativo.is_(True))
            .group_by(Supply.id)
        )

        if so_criticos:
            consulta = consulta.having(
                and_(Supply.estoque_minimo.isnot(None), saldo < Supply.estoque_minimo)
            )

        return consulta

    def saldos(self, categoria: str | None, insumo_id: uuid.UUID | None,
               so_criticos: bool, janela_dias: int, hoje: date,
               limite: int) -> list[dict]:
        consulta = self._base_saldo(so_criticos, janela_dias, hoje)

        if categoria:
            consulta = consulta.filter(_normaliza(Supply.categoria) == _normaliza_texto(categoria))
        if insumo_id:
            consulta = consulta.filter(Supply.id == insumo_id)

        # Mais critico primeiro: quem tem menos saldo em relacao ao minimo.
        consulta = consulta.order_by(
            func.coalesce(func.sum(StockMovement.quantidade_base), 0).asc(),
            Supply.nome.asc(),
        )

        linhas = consulta.limit(limite).all()
        return [self._linha_saldo(linha, janela_dias) for linha in linhas]

    def contar_saldos(self, categoria: str | None, insumo_id: uuid.UUID | None,
                      so_criticos: bool, janela_dias: int, hoje: date) -> int:
        """COUNT de verdade para o bloco truncamento (CONVENCAO_TOOLS.md 4.2)."""
        consulta = self._base_saldo(so_criticos, janela_dias, hoje)
        if categoria:
            consulta = consulta.filter(_normaliza(Supply.categoria) == _normaliza_texto(categoria))
        if insumo_id:
            consulta = consulta.filter(Supply.id == insumo_id)
        return self.db.query(func.count()).select_from(consulta.subquery()).scalar() or 0

    @staticmethod
    def _linha_saldo(linha, janela_dias: int) -> dict:
        saldo = Decimal(linha.saldo or 0)
        consumo = Decimal(linha.consumo_janela or 0)

        # Sem consumo registrado nao ha como estimar cobertura. Devolve null e a
        # rota explica em `avisos` -- nunca zero, que seria lido como "acabou".
        if consumo > 0:
            media_dia = consumo / Decimal(janela_dias)
            cobertura = float(round(saldo / media_dia, 1)) if media_dia > 0 else None
        else:
            cobertura = None

        return {
            "insumo": linha.nome,
            "codigo": linha.codigo,
            "categoria": linha.categoria,
            "saldo": float(round(saldo, 3)),
            "unidade": linha.unidade_base,
            "minimo": float(round(Decimal(linha.estoque_minimo), 3))
            if linha.estoque_minimo is not None else None,
            "cobertura_dias": cobertura,
            "ultima_compra": linha.ultima_compra.date().isoformat()
            if linha.ultima_compra else None,
        }

    # -------------------------------------------------------- 3: preco por insumo

    def historico_preco(self, insumo_id: uuid.UUID, fornecedor_id: uuid.UUID | None,
                        start_date: date | None, end_date: date | None,
                        limite: int) -> list[dict]:
        consulta = (
            self.db.query(
                Purchase.emitida_em,
                Supplier.razao_social,
                PurchaseItem.quantidade_base,
                PurchaseItem.custo_unitario_base,
                PurchaseItem.valor_total,
                PurchaseItem.unidade_fiscal,
                PurchaseItem.quantidade_fiscal,
            )
            .join(Purchase, Purchase.id == PurchaseItem.compra_id)
            .join(Supplier, Supplier.id == Purchase.fornecedor_id)
            .filter(
                PurchaseItem.insumo_id == insumo_id,
                PurchaseItem.custo_unitario_base.isnot(None),
                Purchase.status != "cancelada",
            )
        )
        consulta = self._filtra_periodo(consulta, start_date, end_date)

        if fornecedor_id:
            consulta = consulta.filter(Purchase.fornecedor_id == fornecedor_id)

        linhas = consulta.order_by(Purchase.emitida_em.desc()).limit(limite).all()

        return [
            {
                "data": linha.emitida_em.date().isoformat() if linha.emitida_em else None,
                "fornecedor": linha.razao_social,
                "quantidade": float(round(Decimal(linha.quantidade_base or 0), 3)),
                "custo_unitario": float(round(Decimal(linha.custo_unitario_base or 0), 4)),
                "valor_total": float(round(Decimal(linha.valor_total or 0), 2)),
                "embalagem": f"{linha.quantidade_fiscal} {linha.unidade_fiscal}",
            }
            for linha in linhas
        ]

    def contar_historico_preco(self, insumo_id: uuid.UUID, fornecedor_id: uuid.UUID | None,
                               start_date: date | None, end_date: date | None) -> int:
        consulta = (
            self.db.query(func.count(PurchaseItem.id))
            .join(Purchase, Purchase.id == PurchaseItem.compra_id)
            .filter(
                PurchaseItem.insumo_id == insumo_id,
                PurchaseItem.custo_unitario_base.isnot(None),
                Purchase.status != "cancelada",
            )
        )
        consulta = self._filtra_periodo(consulta, start_date, end_date)
        if fornecedor_id:
            consulta = consulta.filter(Purchase.fornecedor_id == fornecedor_id)
        return consulta.scalar() or 0

    # ------------------------------------------------------------------ 4: CMV

    def cmv_por_insumo(self, start_date: date, end_date: date, limite: int) -> list[dict]:
        """CMV sai do custo gravado no proprio movimento de consumo.

        O custo medio ponderado e calculado no momento da baixa e congelado na
        linha: recalcular depois faria o CMV de agosto mudar quando uma compra de
        setembro entrasse.
        """
        valor = func.coalesce(func.sum(func.abs(StockMovement.valor_total)), 0)

        linhas = (
            self.db.query(
                Supply.nome,
                Supply.unidade_base,
                func.sum(func.abs(StockMovement.quantidade_base)).label("quantidade"),
                valor.label("valor"),
            )
            .join(Supply, Supply.id == StockMovement.insumo_id)
            .filter(
                StockMovement.tipo == "consumo",
                func.date(StockMovement.ocorreu_em) >= start_date,
                func.date(StockMovement.ocorreu_em) <= end_date,
            )
            .group_by(Supply.id)
            .order_by(valor.desc())
            .limit(limite)
            .all()
        )

        return [
            {
                "insumo": linha.nome,
                "quantidade": float(round(Decimal(linha.quantidade or 0), 3)),
                "unidade": linha.unidade_base,
                "custo": float(round(Decimal(linha.valor or 0), 2)),
            }
            for linha in linhas
        ]

    def cmv_totais(self, start_date: date, end_date: date) -> dict:
        total, com_custo, sem_custo = (
            self.db.query(
                func.coalesce(func.sum(func.abs(StockMovement.valor_total)), 0),
                func.count(StockMovement.id).filter(StockMovement.valor_total.isnot(None)),
                func.count(StockMovement.id).filter(StockMovement.valor_total.is_(None)),
            )
            .filter(
                StockMovement.tipo == "consumo",
                func.date(StockMovement.ocorreu_em) >= start_date,
                func.date(StockMovement.ocorreu_em) <= end_date,
            )
            .one()
        )

        insumos_distintos = (
            self.db.query(func.count(func.distinct(StockMovement.insumo_id)))
            .filter(
                StockMovement.tipo == "consumo",
                func.date(StockMovement.ocorreu_em) >= start_date,
                func.date(StockMovement.ocorreu_em) <= end_date,
            )
            .scalar()
        ) or 0

        return {
            "cmv_total": float(round(Decimal(total or 0), 2)),
            "movimentos_com_custo": int(com_custo or 0),
            "movimentos_sem_custo": int(sem_custo or 0),
            "insumos": insumos_distintos,
        }

    # -------------------------------------------------------------- 5: compras

    def _filtra_periodo(self, consulta, start_date: date | None, end_date: date | None):
        if start_date:
            consulta = consulta.filter(func.date(Purchase.emitida_em) >= start_date)
        if end_date:
            consulta = consulta.filter(func.date(Purchase.emitida_em) <= end_date)
        return consulta

    def compras(self, start_date: date | None, end_date: date | None,
                fornecedor_id: uuid.UUID | None, status: str | None,
                limite: int) -> list[dict]:
        pendentes = (
            select(func.count(PurchaseItem.id))
            .where(
                PurchaseItem.compra_id == Purchase.id,
                PurchaseItem.status == "precisa_mapeamento",
            )
            .scalar_subquery()
        )
        total_itens = (
            select(func.count(PurchaseItem.id))
            .where(PurchaseItem.compra_id == Purchase.id)
            .scalar_subquery()
        )

        consulta = (
            self.db.query(
                Purchase.emitida_em,
                Purchase.numero_nota,
                Purchase.valor_total,
                Purchase.status,
                Supplier.razao_social,
                total_itens.label("itens"),
                pendentes.label("pendentes"),
            )
            .join(Supplier, Supplier.id == Purchase.fornecedor_id)
        )
        consulta = self._filtra_periodo(consulta, start_date, end_date)

        if fornecedor_id:
            consulta = consulta.filter(Purchase.fornecedor_id == fornecedor_id)
        if status:
            consulta = consulta.filter(Purchase.status == status)

        linhas = consulta.order_by(Purchase.emitida_em.desc()).limit(limite).all()

        return [
            {
                "data": linha.emitida_em.date().isoformat() if linha.emitida_em else None,
                "fornecedor": linha.razao_social,
                "numero_nota": linha.numero_nota,
                "valor": float(round(Decimal(linha.valor_total or 0), 2)),
                "status": linha.status,
                "itens": int(linha.itens or 0),
                "itens_pendentes": int(linha.pendentes or 0),
            }
            for linha in linhas
        ]

    def contar_compras(self, start_date: date | None, end_date: date | None,
                       fornecedor_id: uuid.UUID | None, status: str | None) -> int:
        consulta = self.db.query(func.count(Purchase.id))
        consulta = self._filtra_periodo(consulta, start_date, end_date)
        if fornecedor_id:
            consulta = consulta.filter(Purchase.fornecedor_id == fornecedor_id)
        if status:
            consulta = consulta.filter(Purchase.status == status)
        return consulta.scalar() or 0

    def totais_compras(self, start_date: date | None, end_date: date | None,
                       fornecedor_id: uuid.UUID | None, status: str | None) -> dict:
        consulta = self.db.query(
            func.coalesce(func.sum(Purchase.valor_total), 0),
            func.count(Purchase.id),
        )
        consulta = self._filtra_periodo(consulta, start_date, end_date)
        if fornecedor_id:
            consulta = consulta.filter(Purchase.fornecedor_id == fornecedor_id)
        if status:
            consulta = consulta.filter(Purchase.status == status)
        valor, quantidade = consulta.one()

        pendentes = (
            self.db.query(func.count(PurchaseItem.id))
            .join(Purchase, Purchase.id == PurchaseItem.compra_id)
            .filter(PurchaseItem.status == "precisa_mapeamento")
        )
        pendentes = self._filtra_periodo(pendentes, start_date, end_date)
        if fornecedor_id:
            pendentes = pendentes.filter(Purchase.fornecedor_id == fornecedor_id)

        return {
            "compras": int(quantidade or 0),
            "valor_total": float(round(Decimal(valor or 0), 2)),
            "itens_pendentes": int(pendentes.scalar() or 0),
        }

    # ------------------------------------------------------------------ escrita

    def compra_por_chave(self, chave_nfe: str) -> Purchase | None:
        return self.db.query(Purchase).filter(Purchase.chave_nfe == chave_nfe).first()

    def documento_por_hash(self, hash_sha256: str) -> Document | None:
        return self.db.query(Document).filter(Document.hash_sha256 == hash_sha256).first()

    def fornecedor_por_cnpj(self, cnpj: str) -> Supplier | None:
        return self.db.query(Supplier).filter(Supplier.cnpj == cnpj).first()

    def mapeamento_vigente(self, fornecedor_id: uuid.UUID, codigo_fiscal: str | None,
                           gtin: str | None) -> SupplierMapping | None:
        """So mapeamento CONFIRMADO e vigente lanca automatico.

        `sugerido` -- inclusive o que a IA propos -- nunca entra por aqui: item
        novo espera confirmacao humana.
        """
        if not codigo_fiscal and not gtin:
            return None

        condicoes = []
        if codigo_fiscal:
            condicoes.append(
                and_(
                    SupplierMapping.fornecedor_id == fornecedor_id,
                    SupplierMapping.codigo_fiscal == codigo_fiscal,
                )
            )
        if gtin:
            condicoes.append(SupplierMapping.gtin == gtin)

        return (
            self.db.query(SupplierMapping)
            .filter(
                SupplierMapping.status == "confirmado",
                SupplierMapping.valid_to.is_(None),
                or_(*condicoes),
            )
            .order_by(SupplierMapping.valid_from.desc())
            .first()
        )

    def insumo_por_codigo(self, codigo: str) -> Supply | None:
        """Casamento exato pelo codigo, sem cair no nome.

        O importador precisa disso: `buscar_insumo_por_nome_ou_codigo` tambem
        casa por nome, e uma planilha com codigo novo cujo nome bate com outro
        insumo viraria atualizacao do insumo errado.
        """
        return (
            self.db.query(Supply)
            .filter(_normaliza(Supply.codigo) == _normaliza_texto(codigo))
            .first()
        )

    def tem_movimento(self, insumo_id: uuid.UUID) -> bool:
        return (
            self.db.query(StockMovement.id)
            .filter(StockMovement.insumo_id == insumo_id)
            .first()
        ) is not None

    def fichas_vigentes(self, eye_product_ids: list[str]) -> dict:
        """Ficha vigente de cada produto, com os itens e o insumo de cada um."""
        from src.models import Recipe, RecipeItem

        fichas = (
            self.db.query(Recipe)
            .filter(Recipe.eye_product_id.in_(eye_product_ids),
                    Recipe.valid_to.is_(None))
            .all()
        )
        if not fichas:
            return {}

        itens = (
            self.db.query(RecipeItem, Supply)
            .join(Supply, Supply.id == RecipeItem.insumo_id)
            .filter(RecipeItem.ficha_tecnica_id.in_([f.id for f in fichas]))
            .all()
        )

        por_ficha = {}
        for item, insumo in itens:
            por_ficha.setdefault(item.ficha_tecnica_id, []).append((item, insumo))

        return {f.eye_product_id: (f, por_ficha.get(f.id, [])) for f in fichas}

    def movimento_por_chave(self, chave: str) -> StockMovement | None:
        return (
            self.db.query(StockMovement)
            .filter(StockMovement.chave_idempotencia == chave)
            .first()
        )

    def item_por_id(self, compra_id: uuid.UUID, item_id: uuid.UUID) -> PurchaseItem | None:
        return (
            self.db.query(PurchaseItem)
            .filter(PurchaseItem.id == item_id, PurchaseItem.compra_id == compra_id)
            .first()
        )

    def itens_pendentes(self, compra_id: uuid.UUID) -> int:
        return (
            self.db.query(func.count(PurchaseItem.id))
            .filter(
                PurchaseItem.compra_id == compra_id,
                PurchaseItem.status == "precisa_mapeamento",
            )
            .scalar()
        ) or 0

    def custo_medio_ponderado(self, insumo_id: uuid.UUID, ate: datetime) -> Decimal | None:
        """Custo medio ponderado das entradas ate a data.

        E o metodo escolhido para o CMV: soma o valor de todas as compras e divide
        pela quantidade que entrou. PEPS exigiria fila de lotes, que este modelo
        deliberadamente nao guarda.
        """
        valor, quantidade = (
            self.db.query(
                func.coalesce(func.sum(StockMovement.valor_total), 0),
                func.coalesce(func.sum(StockMovement.quantidade_base), 0),
            )
            .filter(
                StockMovement.insumo_id == insumo_id,
                StockMovement.tipo == "compra",
                StockMovement.ocorreu_em <= ate,
            )
            .one()
        )

        quantidade = Decimal(quantidade or 0)
        if quantidade <= 0:
            return None

        return (Decimal(valor or 0) / quantidade).quantize(Decimal("0.0001"))

    def despesa_avulsa_compativel(self, valor: Decimal, ate: datetime,
                                  tolerancia: Decimal) -> Expense | None:
        """Despesa lancada pelo comprovante da MESMA compra, ainda sem vinculo.

        Evita que nota e comprovante virem dois lancamentos. Janela de 48h, valor
        com tolerancia, e nenhuma compra ja apontando para ela.
        """
        desde = (ate - timedelta(hours=48)).date()
        ja_vinculadas = select(Purchase.despesa_id).where(Purchase.despesa_id.isnot(None))

        return (
            self.db.query(Expense)
            .filter(
                Expense.data >= desde,
                Expense.data <= ate.date(),
                func.abs(Expense.valor - valor) <= tolerancia,
                Expense.id.notin_(ja_vinculadas),
            )
            .order_by(func.abs(Expense.valor - valor).asc())
            .first()
        )

    def contagem_por_chave(self, chave: str) -> StockCount | None:
        return (
            self.db.query(StockCount)
            .filter(StockCount.chave_idempotencia == chave)
            .first()
        )

    def saldo_atual(self, insumo_id: uuid.UUID) -> Decimal:
        total = (
            self.db.query(func.coalesce(func.sum(StockMovement.quantidade_base), 0))
            .filter(StockMovement.insumo_id == insumo_id)
            .scalar()
        )
        return Decimal(total or 0)

    def compras_aguardando_comprovante(
        self, valor: Decimal, data_pagamento: date, tolerancia: Decimal,
        janela_dias: int,
    ) -> list[tuple[Purchase, Supplier, Expense]]:
        """Compras cuja despesa foi criada pela nota e ainda espera comprovante.

        O JOIN em `Expense` já exclui compra sem despesa — que é a compra
        lançada com `criar_despesa=false`, dinheiro deliberadamente registrado
        por outro caminho. Estoque inicial não pode virar candidato.

        `comprovante_path IS NULL` é o que identifica a despesa sintética: a que
        `_vincula_despesa` criou a partir da nota e que ninguém comprovou ainda.
        Despesa que já veio de um comprovante não entra — aquela já está casada.
        """
        inicio = data_pagamento - timedelta(days=janela_dias)
        fim = data_pagamento + timedelta(days=janela_dias)

        return (
            self.db.query(Purchase, Supplier, Expense)
            .join(Supplier, Supplier.id == Purchase.fornecedor_id)
            .join(Expense, Expense.id == Purchase.despesa_id)
            .filter(
                Purchase.status != "cancelada",
                Expense.comprovante_path.is_(None),
                func.abs(Expense.valor - valor) <= tolerancia,
                Expense.data >= inicio,
                Expense.data <= fim,
            )
            .all()
        )
