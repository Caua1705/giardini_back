"""Leitura do domínio de estoque — as cinco tools da Júlia.

Toda resposta segue docs/CONVENCAO_TOOLS.md: envelope de quatro chaves, números
prontos, teto de 50 linhas, `truncamento.total` de COUNT real.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import FinanceTransaction
from src.repositories.inventory_repository import InventoryRepository
from src.schemas.admin_inventory import JANELA_CONSUMO_DIAS, STATUS_COMPRA_VALIDOS
from src.schemas.tool_envelope import (
    ErroTool,
    Periodo,
    RespostaTool,
    monta_truncamento,
    rotulo_periodo,
)

FUSO = ZoneInfo("America/Fortaleza")


class AdminInventoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InventoryRepository(db)

    # ------------------------------------------------------------------ apoio

    def _hoje(self) -> date:
        return datetime.now(FUSO).date()

    def _resolve_insumo(self, termo: str):
        insumo = self.repo.buscar_insumo_por_nome_ou_codigo(termo)
        if insumo:
            return insumo

        opcoes = self.repo.listar_nomes_de_insumo()
        sugestao = (
            "Os insumos cadastrados são: " + ", ".join(opcoes) + "."
            if opcoes
            else "Ainda não há insumo cadastrado no estoque."
        )
        raise ErroTool(404, "ENTIDADE_NAO_ENCONTRADA",
                       f"Não existe insumo chamado '{termo}'.", sugestao)

    def _resolve_fornecedor(self, termo: str):
        fornecedor = self.repo.buscar_fornecedor_por_nome(termo)
        if fornecedor:
            return fornecedor

        opcoes = self.repo.listar_nomes_de_fornecedor()
        sugestao = (
            "Os fornecedores cadastrados são: " + ", ".join(opcoes) + "."
            if opcoes
            else "Ainda não há fornecedor cadastrado."
        )
        raise ErroTool(404, "ENTIDADE_NAO_ENCONTRADA",
                       f"Não existe fornecedor chamado '{termo}'.", sugestao)

    def _valida_categoria(self, categoria: str | None) -> None:
        if not categoria:
            return
        existentes = self.repo.listar_categorias()
        alvo = categoria.strip().lower()
        if not any(c.strip().lower() == alvo for c in existentes):
            raise ErroTool(
                404, "ENTIDADE_NAO_ENCONTRADA",
                f"Não existe categoria de insumo chamada '{categoria}'.",
                "As categorias existentes são: " + ", ".join(existentes) + "."
                if existentes else "Nenhum insumo tem categoria preenchida ainda.",
            )

    @staticmethod
    def _aviso_cobertura(itens: list[dict]) -> list[str]:
        avisos = [
            f"Cobertura em dias calculada sobre o consumo médio dos últimos "
            f"{JANELA_CONSUMO_DIAS} dias."
        ]
        sem_cobertura = sum(1 for i in itens if i["cobertura_dias"] is None)
        if sem_cobertura:
            avisos.append(
                f"{sem_cobertura} " +
                ("item está" if sem_cobertura == 1 else "itens estão") +
                " sem cobertura calculada porque ainda não há consumo registrado "
                "no período."
            )
        return avisos

    # ------------------------------------------------------------- 1. saldo

    def saldo(self, insumo: str | None, categoria: str | None, limite: int) -> RespostaTool:
        self._valida_categoria(categoria)
        insumo_id = self._resolve_insumo(insumo).id if insumo else None
        hoje = self._hoje()

        itens = self.repo.saldos(categoria, insumo_id, False, JANELA_CONSUMO_DIAS, hoje, limite)
        total = self.repo.contar_saldos(categoria, insumo_id, False, JANELA_CONSUMO_DIAS, hoje)

        avisos = self._aviso_cobertura(itens)
        if total > len(itens):
            avisos.append(f"Mostrando {len(itens)} de {total} insumos, do menor saldo "
                          "para o maior.")

        return RespostaTool(
            # Estoque e foto do agora, nao intervalo. A chave continua presente.
            periodo=None,
            dados={"insumos": total, "itens": itens},
            avisos=avisos,
            truncamento=monta_truncamento(
                len(itens), total,
                "Filtre por categoria ou insumo, ou aumente limite (máx 50).",
            ),
        )

    # ---------------------------------------------------------- 2. críticos

    def criticos(self, categoria: str | None, limite: int) -> RespostaTool:
        self._valida_categoria(categoria)
        hoje = self._hoje()

        itens = self.repo.saldos(categoria, None, True, JANELA_CONSUMO_DIAS, hoje, limite)
        total = self.repo.contar_saldos(categoria, None, True, JANELA_CONSUMO_DIAS, hoje)

        avisos = self._aviso_cobertura(itens)
        if total == 0:
            avisos = ["Nenhum insumo está abaixo do mínimo."]
        elif total > len(itens):
            avisos.append(f"Mostrando os {len(itens)} itens mais críticos de {total} "
                          "abaixo do mínimo.")

        return RespostaTool(
            periodo=None,
            dados={"itens_criticos": total, "itens": itens},
            avisos=avisos,
            truncamento=monta_truncamento(
                len(itens), total,
                "Aumente limite ou filtre por categoria para ver os demais.",
            ),
        )

    # ------------------------------------------------------- 3. preço/insumo

    def historico_preco(self, insumo: str, fornecedor: str | None,
                        start_date: date | None, end_date: date | None,
                        limite: int) -> RespostaTool:
        alvo = self._resolve_insumo(insumo)
        fornecedor_id = self._resolve_fornecedor(fornecedor).id if fornecedor else None

        compras = self.repo.historico_preco(alvo.id, fornecedor_id, start_date, end_date, limite)
        total = self.repo.contar_historico_preco(alvo.id, fornecedor_id, start_date, end_date)

        precos = [c["custo_unitario"] for c in compras if c["custo_unitario"]]
        resumo = {
            "insumo": alvo.nome,
            "unidade": alvo.unidade_base,
            "compras": total,
            "preco_atual": precos[0] if precos else None,
            "preco_medio": round(sum(precos) / len(precos), 4) if precos else None,
            "preco_minimo": min(precos) if precos else None,
            "preco_maximo": max(precos) if precos else None,
            # Variação já calculada: quem consome não divide nada.
            "variacao_pct": (
                round((precos[0] - precos[-1]) / precos[-1] * 100, 1)
                if len(precos) > 1 and precos[-1] else None
            ),
            "historico": compras,
        }

        avisos: list[str] = []
        if total == 0:
            avisos.append(f"Não há compra de {alvo.nome} registrada no período.")
        elif total > len(compras):
            avisos.append(f"Mostrando as {len(compras)} compras mais recentes de {total}.")
        if len(precos) == 1:
            avisos.append("Só há uma compra no período, então não há variação para comparar.")

        return RespostaTool(
            periodo=self._periodo_ou_none(start_date, end_date),
            dados=resumo,
            avisos=avisos,
            truncamento=monta_truncamento(
                len(compras), total,
                "Restrinja o período ou aumente limite (máx 50).",
            ),
        )

    # ---------------------------------------------------------------- 4. CMV

    def cmv(self, start_date: date, end_date: date, limite: int) -> RespostaTool:
        totais = self.repo.cmv_totais(start_date, end_date)
        por_insumo = self.repo.cmv_por_insumo(start_date, end_date, limite)

        receita = self._receita_periodo(start_date, end_date)
        cmv_total = totais["cmv_total"]

        dados = {
            "cmv_total": cmv_total,
            "receita_total": receita,
            # Percentual em pontos percentuais, já dividido.
            "cmv_percentual": (
                round(cmv_total / receita * 100, 1) if receita else None
            ),
            "insumos_consumidos": totais["insumos"],
            "por_insumo": por_insumo,
        }

        avisos = ["CMV calculado por custo médio ponderado, congelado no momento "
                  "de cada baixa."]
        if totais["movimentos_sem_custo"]:
            avisos.append(
                f"{totais['movimentos_sem_custo']} baixas ficaram sem custo porque "
                "o insumo não tinha compra registrada antes; elas não entram no total."
            )
        if not receita:
            avisos.append("Não há receita registrada no período, então o percentual "
                          "não pôde ser calculado.")
        if totais["insumos"] > len(por_insumo):
            avisos.append(f"Mostrando os {len(por_insumo)} insumos de maior custo de "
                          f"{totais['insumos']}.")

        return RespostaTool(
            periodo=self._periodo(start_date, end_date),
            dados=dados,
            avisos=avisos,
            truncamento=monta_truncamento(
                len(por_insumo), totais["insumos"],
                "Aumente limite (máx 50) para ver os demais insumos.",
            ),
        )

    def _receita_periodo(self, start_date: date, end_date: date) -> float | None:
        """Receita do período, só para calcular o CMV percentual.

        Mesma regra do agente_sql: transaction_type '0' e data convertida para
        America/Fortaleza antes de comparar.
        """
        data_local = func.date(
            func.timezone("America/Fortaleza", FinanceTransaction.data_hora)
        )
        total = (
            self.db.query(func.coalesce(func.sum(FinanceTransaction.total), 0))
            .filter(
                FinanceTransaction.transaction_type == "0",
                data_local >= start_date,
                data_local <= end_date,
            )
            .scalar()
        )
        valor = float(total or 0)
        return round(valor, 2) if valor else None

    # ------------------------------------------------------------ 5. compras

    def compras(self, start_date: date | None, end_date: date | None,
                fornecedor: str | None, status: str | None, limite: int) -> RespostaTool:
        if status and status not in STATUS_COMPRA_VALIDOS:
            raise ErroTool(
                400, "PARAMETRO_INVALIDO",
                f"'{status}' não é um status de compra.",
                "Os valores válidos são: " + ", ".join(STATUS_COMPRA_VALIDOS) + ".",
            )

        fornecedor_id = self._resolve_fornecedor(fornecedor).id if fornecedor else None

        itens = self.repo.compras(start_date, end_date, fornecedor_id, status, limite)
        totais = self.repo.totais_compras(start_date, end_date, fornecedor_id, status)
        total = self.repo.contar_compras(start_date, end_date, fornecedor_id, status)

        avisos: list[str] = []
        if totais["itens_pendentes"]:
            avisos.append(
                f"{totais['itens_pendentes']} itens ainda precisam de mapeamento e "
                "não entraram no estoque."
            )
        if total > len(itens):
            avisos.append(f"Mostrando as {len(itens)} compras mais recentes de {total}.")
        if total == 0:
            avisos.append("Não há compra registrada no período.")

        return RespostaTool(
            periodo=self._periodo_ou_none(start_date, end_date),
            dados={
                "compras": totais["compras"],
                "valor_total": totais["valor_total"],
                "itens_pendentes": totais["itens_pendentes"],
                "itens": itens,
            },
            avisos=avisos,
            truncamento=monta_truncamento(
                len(itens), total,
                "Restrinja o período, filtre por fornecedor ou aumente limite (máx 50).",
            ),
        )

    # --------------------------------------------------------------- período

    @staticmethod
    def _periodo(start_date: date, end_date: date) -> Periodo:
        return Periodo(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            rotulo=rotulo_periodo(start_date, end_date),
        )

    @classmethod
    def _periodo_ou_none(cls, start_date: date | None, end_date: date | None) -> Periodo | None:
        if start_date is None or end_date is None:
            return None
        return cls._periodo(start_date, end_date)
