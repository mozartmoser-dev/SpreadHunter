from dataclasses import dataclass, field
from enum import Enum


class TipoEstrutura(Enum):
    BOX_ITM_BASKET = "BOX_ITM_BASKET"
    BOX_3_PERNAS = "BOX_3_PERNAS"
    SBTH = "SBTH"


@dataclass(slots=True)
class EstruturaOperacional:
    oportunidade_id: int | None
    tipo: TipoEstrutura
    coefic_alvo: float
    coefic_mercado: float
    taxa_ganho: float
    id: int | None = None
