import logging

from src.domain.services.market_data_source import FieldName, FASTTRADE_FIELD_STR
from src.infrastructure.providers.rtd_fast_trade import RTDFastTrade

logger = logging.getLogger(__name__)


class FastTradeRTDAdapter:
    """Traduz FieldName → str Fast Trade RTD. Ponte RTDFastTrade (Excel headless)."""

    suporta_push: bool = False
    suporta_cab_skip: bool = True

    def __init__(self, throttle_ms: int = 200):
        self._rtd = RTDFastTrade(throttle_ms=throttle_ms)

    @property
    def disponivel(self) -> bool:
        return self._rtd.disponivel

    def _resolver(self, campo: FieldName | str) -> str:
        if isinstance(campo, FieldName):
            return FASTTRADE_FIELD_STR.get(campo, "")
        return campo

    def registrar_topico(self, codigo: str, campo: FieldName) -> int:
        return self._rtd.registrar_topico(codigo, self._resolver(campo))

    def registrar_lista(self, registros: list[tuple[str, FieldName]]) -> int:
        count = 0
        for codigo, campo in registros:
            if self._rtd.registrar_topico(codigo, self._resolver(campo)) >= 0:
                count += 1
        return count

    def registrar_status(self, codigo: str) -> int:
        return self._rtd.registrar_status(codigo)

    def ler_campo_cache(self, codigo: str, campo: FieldName) -> float | None:
        return self._rtd.ler_campo_cache(codigo, self._resolver(campo))

    def ler_campos(self, codigo: str, *campos: FieldName, allow_stale: bool = False) -> dict[FieldName, float | None]:
        return {c: self.ler_campo_cache(codigo, c) for c in campos}

    def ler_status_cache(self, codigo: str) -> str:
        return self._rtd.ler_status_cache(codigo)

    def forcar_leitura(self, codigo: str, campo: FieldName) -> float | None:
        return self._rtd.forcar_leitura(codigo, self._resolver(campo))

    def refresh(self, timeout_ms: int = 0) -> dict[str, object]:
        return self._rtd.refresh(timeout_ms)

    def reconectar(self, max_attempts: int = 2, delay_s: float = 1.0) -> bool:
        return self._rtd.reconectar(max_attempts=max_attempts, delay_s=delay_s)

    def invalidar_cache(self, codigo: str, campo: FieldName):
        self._rtd.invalidar_cache(codigo, self._resolver(campo))

    def desconectar(self):
        self._rtd.desconectar()

    def get_ts_campo(self, codigo: str, campo: FieldName) -> float | None:
        return self._rtd.get_ts_campo(codigo, self._resolver(campo))

    def get_idade_campo(self, codigo: str, campo: FieldName) -> float | None:
        return self._rtd.get_idade_campo(codigo, self._resolver(campo))
