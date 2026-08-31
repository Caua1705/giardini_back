"""Lançamento de despesa a partir de um comprovante.

Esta é a outra metade de uma invariante só: **nota fiscal e comprovante da
mesma compra não podem virar dois lançamentos.** A primeira metade vive em
`AdminInventoryWriteService._vincula_despesa`, e cobre a ordem
*comprovante → nota*: quando a nota chega, ela procura uma despesa avulsa
compatível e se vincula a ela.

Faltava a ordem inversa. Quando a nota chegava primeiro, ela criava uma
**despesa sintética** (descrição "Compra 123", sem `comprovante_path`), e o
comprovante que chegasse depois era gravado por um insert direto do n8n, que
não sabia da compra. O mesmo dinheiro entrava duas vezes no relatório.

Por isso a despesa passou a ter um dono só: o `insercao_despesas` chama esta
rota em vez de escrever no Supabase. A regra de casamento existe uma vez, com
uma tolerância e uma janela — não duas implementações que divergem.

A janela desta direção é maior (7 dias) que a da direção contrária (48h), e é
de propósito: os custos são assimétricos. Perder o casamento produz um duplo
lançamento silencioso, que ninguém vê; trazer uma candidata a mais produz uma
pergunta no WhatsApp, que é barata e visível.
"""
from datetime import date, datetime

from sqlalchemy.orm import Session

from src.models import Expense
from src.repositories.inventory_repository import InventoryRepository
from src.schemas.admin_expense import DespesaEntrada
from src.services.admin_inventory_write_service import TOLERANCIA_DESPESA
from src.utils.timezone import FORTALEZA_TZ

# Nota paga no ato entra em 48h; boleto do fornecedor, em alguns dias. Ver o
# argumento da assimetria no docstring do módulo.
JANELA_COMPROVANTE_DIAS = 7

CATEGORIA_PADRAO = "NAO_CLASSIFICADO"
DESCRICAO_PADRAO = "Despesa sem descrição"


class AdminExpenseWriteService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InventoryRepository(db)

    def registrar_despesa(self, entrada: DespesaEntrada) -> dict:
        data = entrada.data or datetime.now(FORTALEZA_TZ).date()
        categoria = (entrada.categoria or CATEGORIA_PADRAO).strip() or CATEGORIA_PADRAO
        descricao = (entrada.descricao or "").strip() or DESCRICAO_PADRAO

        candidatas = self.repo.compras_aguardando_comprovante(
            entrada.valor, data, TOLERANCIA_DESPESA, JANELA_COMPROVANTE_DIAS
        )
        # Mais perto do dia do pagamento primeiro: entre duas notas do mesmo
        # valor, a da véspera é mais provável que a da semana passada.
        candidatas.sort(key=lambda c: (abs((c[2].data - data).days),
                                       abs(c[2].valor - entrada.valor)))

        try:
            if len(candidatas) == 1:
                resposta = self._anexa(candidatas[0], entrada, descricao)
            else:
                resposta = self._cria(entrada, data, categoria, descricao, candidatas)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return resposta

    # ------------------------------------------------------------------ casos

    def _anexa(self, candidata, entrada: DespesaEntrada, descricao: str) -> dict:
        """Uma nota só esperava este comprovante. Completa, não lança de novo."""
        compra, fornecedor, despesa = candidata

        despesa.comprovante_path = entrada.comprovante_path
        # `data`, `valor` e `categoria` da despesa NÃO são reescritos. Ela já
        # existe e já pode ter saído num relatório; mudar a data a moveria de
        # dia depois do fato. O que faltava nela era a prova do pagamento.
        if descricao != DESCRICAO_PADRAO and descricao not in (despesa.descricao or ""):
            despesa.descricao = f"{despesa.descricao} — {descricao}"
        self.db.flush()

        return {
            "acao": "anexada",
            "despesa_id": despesa.id,
            "valor": despesa.valor,
            "data": despesa.data,
            "categoria": despesa.categoria,
            "compra_id": str(compra.id),
            "fornecedor": fornecedor.razao_social,
            "numero_nota": compra.numero_nota,
            "candidatas": [],
        }

    def _cria(self, entrada: DespesaEntrada, data: date, categoria: str,
              descricao: str, candidatas: list) -> dict:
        """Nenhuma candidata, ou candidatas demais.

        Nos dois casos a despesa é gravada: dinheiro que passou não pode ficar
        sem registro esperando alguém responder. Quando há candidatas demais,
        elas voltam na resposta para uma pessoa desempatar.
        """
        despesa = Expense(
            descricao=descricao,
            data=data,
            valor=entrada.valor,
            categoria=categoria,
            comprovante_path=entrada.comprovante_path,
        )
        self.db.add(despesa)
        self.db.flush()

        return {
            "acao": "ambiguo" if candidatas else "criada",
            "despesa_id": despesa.id,
            "valor": despesa.valor,
            "data": despesa.data,
            "categoria": despesa.categoria,
            "compra_id": None,
            "fornecedor": None,
            "numero_nota": None,
            "candidatas": [
                {
                    "compra_id": str(compra.id),
                    "despesa_id": desp.id,
                    "fornecedor": forn.razao_social,
                    "numero_nota": compra.numero_nota,
                    "valor": desp.valor,
                    "emitida_em": desp.data,
                }
                for compra, forn, desp in candidatas
            ],
        }
