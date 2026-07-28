from enum import Enum, auto
from typing import Protocol, runtime_checkable


class FieldName(Enum):
    STRIKE = auto()
    LAST_PRICE = auto()
    BID = auto()
    ASK = auto()
    STATUS = auto()
    QTD_LAST = auto()
    VOL_BID = auto()
    VOL_ASK = auto()
    BOOK_HEADER = auto()
    HIGH = auto()
    LOW = auto()
    OPEN = auto()
    CLOSE = auto()
    VOLUME = auto()
    VOLUME_FIN = auto()
    VARIATION = auto()


PROFIT_FIELD_STR: dict[FieldName, str] = {
    FieldName.STRIKE:       "PEX",
    FieldName.LAST_PRICE:   "ULT",
    FieldName.BID:          "OCP",
    FieldName.ASK:          "OVD",
    FieldName.STATUS:       "EST",
    FieldName.QTD_LAST:     "QUL",
    FieldName.VOL_BID:      "VOC",
    FieldName.VOL_ASK:      "VOV",
    FieldName.BOOK_HEADER:  "CAB",
    FieldName.CLOSE:        "PRI",
    FieldName.VARIATION:    "VAR",
}

OPENFAST_FIELD_STR: dict[FieldName, str] = {
    FieldName.STRIKE:       "PEX",
    FieldName.LAST_PRICE:   "LAST",
    FieldName.BID:          "BID",
    FieldName.ASK:          "ASK",
    FieldName.STATUS:       "ST",
    FieldName.QTD_LAST:     "QTLAST",
    FieldName.VOL_BID:      "VOLBID",
    FieldName.VOL_ASK:      "VOLASK",
    FieldName.CLOSE:        "CLOSE",
    FieldName.OPEN:         "OPEN",
    FieldName.VARIATION:    "VAR",
}


@runtime_checkable
class MarketDataSource(Protocol):
    disponivel: bool
    suporta_push: bool
    suporta_cab_skip: bool

    def registrar_topico(self, codigo: str, campo: FieldName) -> int: ...
    def registrar_lista(self, registros: list[tuple[str, FieldName]]) -> int: ...
    def registrar_status(self, codigo: str) -> int: ...
    def ler_campo_cache(self, codigo: str, campo: FieldName) -> float | None: ...
    def ler_campos(self, codigo: str, *campos: FieldName) -> dict[FieldName, float | None]: ...
    def ler_status_cache(self, codigo: str) -> str: ...
    def forcar_leitura(self, codigo: str, campo: FieldName) -> float | None: ...
    def refresh(self, timeout_ms: int = 0) -> dict[str, object]: ...
    def desconectar(self): ...
    def reconectar(self) -> bool: ...
    def invalidar_cache(self, codigo: str, campo: FieldName): ...


def criar_data_source(fonte: str, **kwargs) -> MarketDataSource:
    if fonte == "openfast":
        from src.infrastructure.providers.openfast_socket_adapter import OpenFastSocketAdapter
        adapter = OpenFastSocketAdapter()
        if "send_delay_ms" in kwargs:
            adapter.set_send_delay(kwargs["send_delay_ms"])
        return adapter
    if fonte == "mock":
        from src.infrastructure.providers.mock_market_data import MockDataSource
        return MockDataSource(db_path=kwargs.get("db_path"))
    from src.infrastructure.providers.rtd_profit_adapter import RTDProfitAdapter
    return RTDProfitAdapter()
