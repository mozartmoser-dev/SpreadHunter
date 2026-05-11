from dataclasses import dataclass, field
from enum import Enum


class ClassificacaoOp(Enum):
    BOX_1 = "1BOX"
    SBTH_2 = "2SBTH"
    BOXSBTH_3 = "3BOXSBTH"
    TP_OP = "TP.Op"


@dataclass
class Oportunidade:
    instrumento_id: int
    preco_ativo: float
    strike: float
    dias: int
    cdi_periodo: float
    custo_sbth: float
    pct_ganho_sbth: float
    pct_cdi_sbth: float
    custo_box: float
    pct_ganho_box: float
    pct_cdi_box: float
    classificacao: ClassificacaoOp
    operacao: str
    snapshot_mercado: dict = field(default_factory=dict)
    id: int | None = None

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
