from dataclasses import dataclass, field
from enum import Enum


class ClassificacaoOp (Enum):
    BOX_1 = "1BOX"
    SBTH_2 = "2SBTH"
    TP_OP = "TP.Op"


@dataclass
class Oportunidade:
    instrumento_id: int
    preco_ativo: float
    strike: float
    dias: int
    cdi_periodo: float
    custo_sbth: float
    ganho_sbth: float
    custo_box: float
    ganho_box: float
    classificacao: ClassificacaoOp
    operacao: str
    snapshot_mercado: dict = field(default_factory=dict)
    id: int | None = None

    @property
    def percent_cdi_sbth(self) -> float:
        if self.custo_sbth == 0:
            return 0.0
        return (self.ganho_sbth / self.custo_sbth) * 100

    @property
    def percent_cdi_box(self) -> float:
        if self.custo_box == 0:
            return 0.0
        return (self.ganho_box / self.custo_box) * 100

    @property
    def liq_put_x_lote(self) -> float:
        return self.snapshot_mercado.get("liq_put_x_lote", 0.0)

    @property
    def liq_call_x_lote(self) -> float:
        return self.snapshot_mercado.get("liq_call_x_lote", 0.0)

    @property
    def em_leilao(self) -> bool:
        return self.snapshot_mercado.get("em_leilao", False)

    @property
    def status_put(self) -> str:
        return self.snapshot_mercado.get("status_put", "")

    @property
    def status_call(self) -> str:
        return self.snapshot_mercado.get("status_call", "")

    @property
    def status_ativo(self) -> str:
        return self.snapshot_mercado.get("status_ativo", "")
