from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class TaxaAluguel:
    ativo: str
    data: date
    taxa_atual: float
    taxa_7d: float
    taxa_28d: float
    created_at: datetime | None = None
    id: int | None = None
