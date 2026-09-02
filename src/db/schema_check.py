"""Confere, antes de servir, que o banco tem o que os models declaram.

Existe por causa de um prejuízo medido. O deploy de 31/08/2026 subiu o commit
que adicionou `Expense.identificador_transacao`, mas
`migrations/20260831_despesas_identificador_transacao.sql` nunca foi aplicado.
Como o SQLAlchemy monta o SELECT a partir do model, **toda** consulta que toca
`Expense` passou a pedir uma coluna inexistente — e o estrago não ficou na
feature nova: `GET /admin/finance/expenses`, que é leitura e não usa
identificador nenhum, respondeu 500 em 100% das chamadas por 40 horas. Ninguém
percebeu. O que denunciou foi um comprovante de WhatsApp falhando.

Não há alembic aqui: os `.sql` de `migrations/` são aplicados à mão, e nada no
deploy confere se o schema bate com os models. Este módulo é essa conferência.

**Só uma direção: model ⊆ banco.** Coluna declarada e ausente é fatal — é o bug
acima. Coluna no banco e não no model é normal e não é erro: `despesas` tem
`created_at` e `updated_at`, que nenhum model mapeia. Exigir igualdade
quebraria num banco saudável.

**Só presença — não tipo, não nullability.** Comparar `Numeric` com `numeric`
ou `Mapped[str | None]` com `is_nullable` é um pântano de falso positivo, e
falso positivo é o que faz alguém desligar o check. Coluna faltando é
inequívoco, e é a classe de erro que custou as 40 horas. Divergência de tipo é
rara e falha com erro claro na hora do uso.
"""
import os
import sys

from sqlalchemy import Engine, text

# Importar o pacote popula `Base.metadata`: o `__init__` traz os 21 models, e
# sem ele a conferência passaria por não conhecer tabela nenhuma.
import src.models  # noqa: F401
from src.db.base import Base


VARIAVEL_ESCOTILHA = "SKIP_SCHEMA_CHECK"


def _declarado() -> dict[tuple[str, str], set[str]]:
    """O que os models dizem que existe, por (schema, tabela)."""
    return {
        (tabela.schema or "public", tabela.name): {c.name for c in tabela.columns}
        for tabela in Base.metadata.tables.values()
    }


def _real(engine: Engine, schemas: set[str]) -> dict[tuple[str, str], set[str]]:
    """O que o banco de fato tem, nos schemas que os models usam.

    Uma query só. `information_schema` mostra apenas o que a role enxerga, então
    tabela invisível por permissão apareceria como ausente — é conservador na
    direção certa: prefere recusar a subir a servir um schema que não dá para
    conferir.
    """
    consulta = text(
        "select table_schema, table_name, column_name "
        "from information_schema.columns "
        "where table_schema = any(:schemas)"
    )

    real: dict[tuple[str, str], set[str]] = {}
    with engine.connect() as conn:
        for schema, tabela, coluna in conn.execute(
            consulta, {"schemas": sorted(schemas)}
        ):
            real.setdefault((schema, tabela), set()).add(coluna)
    return real


def divergencias(engine: Engine) -> list[str]:
    """O que os models pedem e o banco não tem. Lista vazia é banco em dia."""
    declarado = _declarado()
    real = _real(engine, {schema for schema, _ in declarado})

    faltando: list[str] = []
    for (schema, tabela), colunas in sorted(declarado.items()):
        existentes = real.get((schema, tabela))
        if existentes is None:
            faltando.append(f"{schema}.{tabela} (tabela inteira)")
            continue
        faltando.extend(
            f"{schema}.{tabela}.{coluna}" for coluna in sorted(colunas - existentes)
        )
    return faltando


def verifica_schema(engine: Engine) -> bool:
    """Levanta se o banco estiver atrás dos models. Chamada no startup.

    Devolve se a conferência de fato rodou — `False` quando a escotilha a
    desligou. Quem escreve a mensagem final precisa dessa distinção: dizer
    "banco em dia" depois de pular a checagem seria mentira.
    """
    if os.getenv(VARIAVEL_ESCOTILHA, "").strip().lower() in {"1", "true", "yes"}:
        print(
            f"schema_check: PULADO por {VARIAVEL_ESCOTILHA} -- "
            "o banco nao foi conferido",
            flush=True,
        )
        return False

    faltando = divergencias(engine)
    if not faltando:
        return True

    raise RuntimeError(
        "schema desatualizado -- o banco nao tem o que os models declaram:\n"
        + "\n".join(f"  {item}" for item in faltando)
        + "\n\naplique as migracoes pendentes de migrations/ e suba de novo."
        + f"\n(para subir assim mesmo: {VARIAVEL_ESCOTILHA}=1)"
    )


if __name__ == "__main__":
    # Preflight do deploy: `docker compose run --rm giardini-api python -m
    # src.db.schema_check` roda num container descartável, contra o banco de
    # produção, sem encostar no container que está servindo. Saída 0 libera o
    # `up -d`; saída 1 aborta o deploy com o antigo ainda de pé.
    from src.db.session import engine

    try:
        conferiu = verifica_schema(engine)
    except RuntimeError as erro:
        print(erro, file=sys.stderr)
        raise SystemExit(1)

    if conferiu:
        print("schema_check: ok, banco em dia com os models")
