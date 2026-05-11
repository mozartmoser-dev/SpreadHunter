from dataclasses import dataclass
from enum import Enum


class Lado(Enum):
    COMPRA = "C"
    VENDA = "V"


@dataclass
class PernaOperacao:
    estrutura_id: int
    codigo: str
    lado: Lado
    quantidade: int
    profundidade: int
    ordem: int
    id: int | None = None
