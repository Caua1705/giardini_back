from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, Query


@dataclass(frozen=True)
class DateRange:
    """Intervalo de datas resolvido a partir dos nomes canonicos e dos aliases legados."""

    start_date: date | None
    end_date: date | None

    @property
    def is_empty(self) -> bool:
        return self.start_date is None and self.end_date is None

    def require_both_or_none(self) -> "DateRange":
        """Rejeita intervalo pela metade em rotas onde ele e opcional."""
        if (self.start_date is None) != (self.end_date is None):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Informe start_date e end_date juntos, ou nenhum dos dois "
                    "para usar o periodo padrao da rota."
                ),
            )

        return self

    def require_both(self) -> tuple[date, date]:
        if self.start_date is None or self.end_date is None:
            raise HTTPException(
                status_code=400,
                detail="Informe start_date e end_date no formato YYYY-MM-DD.",
            )

        return self.start_date, self.end_date


def date_range_params(
    start_date: date | None = Query(
        default=None,
        description="Data inicial do periodo (YYYY-MM-DD). Alias legado aceito: start.",
    ),
    end_date: date | None = Query(
        default=None,
        description="Data final do periodo (YYYY-MM-DD). Alias legado aceito: end.",
    ),
    start: date | None = Query(
        default=None,
        deprecated=True,
        description="Alias legado de start_date. Prefira start_date.",
    ),
    end: date | None = Query(
        default=None,
        deprecated=True,
        description="Alias legado de end_date. Prefira end_date.",
    ),
) -> DateRange:
    """Aceita start_date/end_date (canonico) e start/end (legado, mantido para o n8n)."""
    resolved_start = start_date if start_date is not None else start
    resolved_end = end_date if end_date is not None else end

    if resolved_start and resolved_end and resolved_start > resolved_end:
        raise HTTPException(
            status_code=400,
            detail="start_date deve ser anterior ou igual a end_date.",
        )

    return DateRange(start_date=resolved_start, end_date=resolved_end)
