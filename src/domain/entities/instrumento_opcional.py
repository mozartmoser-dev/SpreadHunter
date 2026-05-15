from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class TipoOpcao(Enum):
    AMERICANA = "A"
    EUROPEIA = "E"


@dataclass
class InstrumentoOpcional:
    ativo: str
    cod_put: str
    cod_call: str
    vencimento: date
    tipo_opcao: TipoOpcao
    id: int | None = None

    @property
    def dias_ate_vencimento(self) -> int:
        if self.vencimento is None:
            return 0
        delta = (self.vencimento - date.today()).days
        return max(delta, 0)
