"""Escrita do domínio de estoque.

NÃO é tool. A `CONVENCAO_TOOLS.md` cobre só leitura ("Só GET. Toda tool é
leitura."); estas rotas seguem o padrão administrativo do
`PATCH /admin/reservations/{id}/status`: corpo próprio, erro `{"detail": ...}`,
e nunca entram na lista de ferramentas da Júlia.

Três invariantes valem em todos os métodos:

1. **Uma transação.** Os N itens de uma nota entram juntos ou nenhum entra.
2. **Idempotência determinística.** Repetir a requisição não duplica: a compra
   pela chave da NFC-e, o documento pelo hash, o movimento pela sua chave.
3. **IA não decide conversão.** Só mapeamento `confirmado` e vigente lança
   automático. Item novo entra como `precisa_mapeamento` e não gera movimento —
   mas não aborta a compra.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
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
from src.repositories.inventory_repository import InventoryRepository
from src.schemas.admin_inventory import (
    CompraEntrada,
    ContagemEntrada,
    MapearItemEntrada,
    PerdaEntrada,
)

TOLERANCIA_DESPESA = Decimal("0.05")


class AdminInventoryWriteService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InventoryRepository(db)

    # ==================================================================== compra

    def registrar_compra(self, entrada: CompraEntrada) -> dict:
        if entrada.chave_nfe:
            existente = self.repo.compra_por_chave(entrada.chave_nfe)
            if existente:
                # Idempotente: a nota já entrou. Nada é criado, nada é alterado.
                return self._resposta_compra(existente, ja_existia=True)

        try:
            compra = self._monta_compra(entrada)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            # Corrida: outra requisição registrou a mesma nota entre a checagem e
            # o commit. O índice único fez seu trabalho; devolvemos a que venceu.
            if entrada.chave_nfe:
                existente = self.repo.compra_por_chave(entrada.chave_nfe)
                if existente:
                    return self._resposta_compra(existente, ja_existia=True)
            raise
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(compra)
        return self._resposta_compra(compra, ja_existia=False)

    def _monta_compra(self, entrada: CompraEntrada) -> Purchase:
        fornecedor = self._obtem_fornecedor(entrada)
        documento = self._obtem_documento(entrada)

        emitida_em = entrada.emitida_em or datetime.now(timezone.utc)

        compra = Purchase(
            documento_id=documento.id if documento else None,
            fornecedor_id=fornecedor.id,
            chave_nfe=entrada.chave_nfe,
            numero_nota=entrada.numero_nota,
            serie=entrada.serie,
            emitida_em=emitida_em,
            valor_total=entrada.valor_total,
            valor_desconto=entrada.valor_desconto,
            status="rascunho",
        )
        self.db.add(compra)
        self.db.flush()

        pendentes = 0
        for item_entrada in entrada.itens:
            item = PurchaseItem(
                compra_id=compra.id,
                ordem=item_entrada.ordem,
                descricao_fiscal=item_entrada.descricao_fiscal,
                codigo_fiscal=item_entrada.codigo_fiscal,
                ncm=item_entrada.ncm,
                cfop=item_entrada.cfop,
                gtin=item_entrada.gtin,
                quantidade_fiscal=item_entrada.quantidade_fiscal,
                unidade_fiscal=item_entrada.unidade_fiscal,
                valor_unitario=item_entrada.valor_unitario,
                valor_total=item_entrada.valor_total,
                status="precisa_mapeamento",
            )

            mapeamento = self.repo.mapeamento_vigente(
                fornecedor.id, item_entrada.codigo_fiscal, item_entrada.gtin
            )

            if mapeamento is None:
                # Item novo não aborta a nota: entra pendente e espera humano.
                pendentes += 1
                self.db.add(item)
                self.db.flush()
                continue

            self._aplica_mapeamento(item, mapeamento)
            self.db.add(item)
            self.db.flush()
            self._movimento_de_compra(item, mapeamento, emitida_em)

        compra.status = "revisao" if pendentes else "lancada"
        if not pendentes:
            compra.lancada_em = datetime.now(timezone.utc)

        self._vincula_despesa(compra, emitida_em)
        return compra

    def _obtem_fornecedor(self, entrada: CompraEntrada) -> Supplier:
        if entrada.fornecedor.cnpj:
            existente = self.repo.fornecedor_por_cnpj(entrada.fornecedor.cnpj)
            if existente:
                return existente

        fornecedor = Supplier(
            cnpj=entrada.fornecedor.cnpj,
            razao_social=entrada.fornecedor.razao_social,
            nome_fantasia=entrada.fornecedor.nome_fantasia,
        )
        self.db.add(fornecedor)
        self.db.flush()
        return fornecedor

    def _obtem_documento(self, entrada: CompraEntrada) -> Document | None:
        if entrada.documento is None:
            return None

        existente = self.repo.documento_por_hash(entrada.documento.hash_sha256)
        if existente:
            # Mesmo arquivo já recebido: reaproveita em vez de duplicar.
            existente.status = "processado"
            existente.processado_em = datetime.now(timezone.utc)
            if entrada.chave_nfe and not existente.chave_nfe:
                existente.chave_nfe = entrada.chave_nfe
            return existente

        documento = Document(
            hash_sha256=entrada.documento.hash_sha256,
            tipo=entrada.documento.tipo,
            nome_arquivo=entrada.documento.nome_arquivo,
            mime=entrada.documento.mime,
            tamanho_bytes=entrada.documento.tamanho_bytes,
            storage_path=entrada.documento.storage_path,
            chave_nfe=entrada.chave_nfe,
            status="processado",
            processado_em=datetime.now(timezone.utc),
        )
        self.db.add(documento)
        self.db.flush()
        return documento

    @staticmethod
    def _aplica_mapeamento(item: PurchaseItem, mapeamento: SupplierMapping) -> None:
        quantidade_base = item.quantidade_fiscal * mapeamento.fator_conversao

        item.insumo_id = mapeamento.insumo_id
        item.mapeamento_id = mapeamento.id
        item.fator_aplicado = mapeamento.fator_conversao
        item.quantidade_base = quantidade_base
        item.custo_unitario_base = (
            (item.valor_total / quantidade_base).quantize(Decimal("0.0001"))
            if quantidade_base > 0 else None
        )
        item.status = "mapeado"

    def _movimento_de_compra(self, item: PurchaseItem, mapeamento: SupplierMapping,
                             ocorreu_em: datetime) -> StockMovement | None:
        chave = f"compra:{item.id}"
        if self.repo.movimento_por_chave(chave):
            return None

        # A unidade base entra como snapshot na linha do movimento.
        unidade = self.db.query(Supply.unidade_base).filter(
            Supply.id == mapeamento.insumo_id
        ).scalar()

        movimento = StockMovement(
            insumo_id=mapeamento.insumo_id,
            tipo="compra",
            quantidade_base=item.quantidade_base,
            # Snapshot: corrigir o mapeamento amanhã não reescreve isto.
            unidade_base=unidade,
            fator_usado=mapeamento.fator_conversao,
            custo_unitario=item.custo_unitario_base,
            valor_total=item.valor_total,
            compra_item_id=item.id,
            ocorreu_em=ocorreu_em,
            chave_idempotencia=chave,
        )
        self.db.add(movimento)
        self.db.flush()
        return movimento

    def _vincula_despesa(self, compra: Purchase, emitida_em: datetime) -> None:
        """Nota e comprovante da mesma compra não podem virar duas despesas."""
        if compra.despesa_id:
            return

        candidata = self.repo.despesa_avulsa_compativel(
            compra.valor_total, emitida_em, TOLERANCIA_DESPESA
        )
        if candidata:
            compra.despesa_id = candidata.id
            return

        despesa = Expense(
            descricao=f"Compra {compra.numero_nota or compra.chave_nfe or compra.id}",
            data=emitida_em.date(),
            valor=compra.valor_total,
            categoria="INSUMOS",
        )
        self.db.add(despesa)
        self.db.flush()
        compra.despesa_id = despesa.id

    def _resposta_compra(self, compra: Purchase, ja_existia: bool) -> dict:

        itens = (
            self.db.query(PurchaseItem, Supply.nome)
            .outerjoin(Supply, Supply.id == PurchaseItem.insumo_id)
            .filter(PurchaseItem.compra_id == compra.id)
            .order_by(PurchaseItem.ordem)
            .all()
        )
        fornecedor = self.db.get(Supplier, compra.fornecedor_id)

        mapeados = sum(1 for item, _ in itens if item.status == "mapeado")
        pendentes = sum(1 for item, _ in itens if item.status == "precisa_mapeamento")

        return {
            "id": str(compra.id),
            "chave_nfe": compra.chave_nfe,
            "fornecedor": fornecedor.razao_social if fornecedor else "",
            "numero_nota": compra.numero_nota,
            "valor_total": compra.valor_total,
            "status": compra.status,
            "ja_existia": ja_existia,
            "itens_total": len(itens),
            "itens_mapeados": mapeados,
            "itens_pendentes": pendentes,
            "despesa_id": compra.despesa_id,
            "despesa_vinculada": compra.despesa_id is not None,
            "itens": [
                {
                    "id": str(item.id),
                    "ordem": item.ordem,
                    "descricao_fiscal": item.descricao_fiscal,
                    "codigo_fiscal": item.codigo_fiscal,
                    "quantidade_fiscal": item.quantidade_fiscal,
                    "unidade_fiscal": item.unidade_fiscal,
                    "valor_total": item.valor_total,
                    "status": item.status,
                    "insumo": nome,
                    "quantidade_base": item.quantidade_base,
                }
                for item, nome in itens
            ],
        }

    # ============================================== confirmar mapeamento de item

    def mapear_item(self, compra_id: uuid.UUID, item_id: uuid.UUID,
                    entrada: MapearItemEntrada) -> dict:

        item = self.repo.item_por_id(compra_id, item_id)
        if item is None:
            raise HTTPException(404, "Item de compra não encontrado.")
        if item.status == "mapeado":
            raise HTTPException(409, "Este item já está mapeado.")

        insumo = self.repo.buscar_insumo_por_nome_ou_codigo(entrada.insumo_codigo)
        if insumo is None:
            raise HTTPException(404, f"Não existe insumo '{entrada.insumo_codigo}'.")

        compra = self.db.get(Purchase, compra_id)
        agora = datetime.now(timezone.utc)

        try:
            # Versionamento: a vigente é fechada, nunca sobrescrita. O gatilho do
            # banco recusa UPDATE nas colunas de identidade.
            anterior = self.repo.mapeamento_vigente(
                compra.fornecedor_id, item.codigo_fiscal, item.gtin
            )
            if anterior is not None:
                anterior.valid_to = agora

            mapeamento = SupplierMapping(
                fornecedor_id=compra.fornecedor_id,
                codigo_fiscal=item.codigo_fiscal or item.descricao_fiscal,
                descricao_fiscal=item.descricao_fiscal,
                gtin=item.gtin,
                insumo_id=insumo.id,
                unidade_fiscal=entrada.unidade_fiscal,
                fator_conversao=entrada.fator_conversao,
                status="confirmado",
                origem="humano",
                valid_from=agora,
                confirmado_por=entrada.confirmado_por,
                confirmado_em=agora,
                observacao=entrada.observacao,
            )
            self.db.add(mapeamento)
            self.db.flush()

            self._aplica_mapeamento(item, mapeamento)
            movimento = self._movimento_de_compra(
                item, mapeamento, compra.emitida_em or agora
            )

            pendentes = self.repo.itens_pendentes(compra_id)
            if pendentes == 0 and compra.status == "revisao":
                compra.status = "lancada"
                compra.lancada_em = agora

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "mapeamento_id": str(mapeamento.id),
            "compra_id": str(compra_id),
            "item_id": str(item_id),
            "insumo": insumo.nome,
            "fator_conversao": entrada.fator_conversao,
            "quantidade_base": item.quantidade_base,
            "custo_unitario_base": item.custo_unitario_base,
            "movimento_id": str(movimento.id) if movimento else None,
            "compra_status": compra.status,
            "itens_pendentes": pendentes,
            "substituiu_mapeamento_id": str(anterior.id) if anterior else None,
        }

    # ================================================================= contagem

    def registrar_contagem(self, entrada: ContagemEntrada) -> dict:
        existente = self.repo.contagem_por_chave(entrada.chave_idempotencia)
        if existente:
            return self._resposta_contagem(existente, ja_existia=True)

        try:
            contagem = StockCount(
                realizada_em=entrada.realizada_em,
                responsavel=entrada.responsavel,
                observacao=entrada.observacao,
                chave_idempotencia=entrada.chave_idempotencia,
                status="aberta",
            )
            self.db.add(contagem)
            self.db.flush()

            ajustes = 0
            for item_entrada in entrada.itens:
                insumo = self.repo.buscar_insumo_por_nome_ou_codigo(
                    item_entrada.insumo_codigo
                )
                if insumo is None:
                    raise HTTPException(
                        404, f"Não existe insumo '{item_entrada.insumo_codigo}'."
                    )

                item = StockCountItem(
                    contagem_id=contagem.id,
                    insumo_id=insumo.id,
                    quantidade_contada=item_entrada.quantidade_contada,
                    observacao=item_entrada.observacao,
                )

                if entrada.fechar:
                    # Snapshot do saldo no fechamento: é o que dá sentido à diferença.
                    item.quantidade_sistema = self.repo.saldo_atual(insumo.id)

                self.db.add(item)
                self.db.flush()

                if entrada.fechar:
                    diferenca = item.quantidade_contada - item.quantidade_sistema
                    if diferenca != 0:
                        self.db.add(StockMovement(
                            insumo_id=insumo.id,
                            tipo="ajuste_contagem",
                            quantidade_base=diferenca,
                            unidade_base=insumo.unidade_base,
                            contagem_item_id=item.id,
                            ocorreu_em=entrada.realizada_em,
                            observacao=f"Contagem de {entrada.responsavel}",
                            chave_idempotencia=f"contagem:{item.id}",
                        ))
                        ajustes += 1

            if entrada.fechar:
                contagem.status = "fechada"
                contagem.fechada_em = datetime.now(timezone.utc)

            self.db.commit()
        except HTTPException:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(contagem)
        return self._resposta_contagem(contagem, ja_existia=False)

    def _resposta_contagem(self, contagem: StockCount, ja_existia: bool) -> dict:

        itens = (
            self.db.query(StockCountItem, Supply.nome, StockMovement.id)
            .join(Supply, Supply.id == StockCountItem.insumo_id)
            .outerjoin(StockMovement, StockMovement.contagem_item_id == StockCountItem.id)
            .filter(StockCountItem.contagem_id == contagem.id)
            .order_by(Supply.nome)
            .all()
        )

        return {
            "id": str(contagem.id),
            "status": contagem.status,
            "ja_existia": ja_existia,
            "ajustes_gerados": sum(1 for _, _, mov in itens if mov is not None),
            "itens": [
                {
                    "insumo": nome,
                    "quantidade_contada": item.quantidade_contada,
                    "quantidade_sistema": item.quantidade_sistema,
                    "diferenca": item.diferenca,
                    "movimento_id": str(mov) if mov else None,
                }
                for item, nome, mov in itens
            ],
        }

    # ==================================================================== perda

    def lancar_perda(self, entrada: PerdaEntrada) -> dict:
        chave = f"perda:{entrada.chave_idempotencia}"

        existente = self.repo.movimento_por_chave(chave)
        if existente:
            return self._resposta_perda(existente, ja_existia=True)

        insumo = self.repo.buscar_insumo_por_nome_ou_codigo(entrada.insumo_codigo)
        if insumo is None:
            raise HTTPException(404, f"Não existe insumo '{entrada.insumo_codigo}'.")

        ocorreu_em = entrada.ocorreu_em or datetime.now(timezone.utc)
        custo = self.repo.custo_medio_ponderado(insumo.id, ocorreu_em)

        try:
            movimento = StockMovement(
                insumo_id=insumo.id,
                tipo="perda",
                # Corpo manda quantidade positiva; o movimento é sempre negativo.
                quantidade_base=-entrada.quantidade,
                unidade_base=insumo.unidade_base,
                custo_unitario=custo,
                valor_total=(
                    (custo * entrada.quantidade).quantize(Decimal("0.01"))
                    if custo is not None else None
                ),
                ocorreu_em=ocorreu_em,
                observacao=entrada.motivo,
                chave_idempotencia=chave,
            )
            self.db.add(movimento)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existente = self.repo.movimento_por_chave(chave)
            if existente:
                return self._resposta_perda(existente, ja_existia=True)
            raise
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(movimento)
        return self._resposta_perda(movimento, ja_existia=False)

    def _resposta_perda(self, movimento: StockMovement, ja_existia: bool) -> dict:

        nome = self.db.query(Supply.nome).filter(
            Supply.id == movimento.insumo_id
        ).scalar()

        return {
            "movimento_id": str(movimento.id),
            "insumo": nome,
            "quantidade": abs(movimento.quantidade_base),
            "unidade_base": movimento.unidade_base,
            "ja_existia": ja_existia,
        }
