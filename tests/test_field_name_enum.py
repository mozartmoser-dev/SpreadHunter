import pytest
from src.domain.services.market_data_source import (
    FieldName,
    PROFIT_FIELD_STR,
    OPENFAST_FIELD_STR,
    MarketDataSource,
    criar_data_source,
)


class TestFieldNameEnum:
    def test_todos_os_campos_definidos(self):
        expected = [
            "STRIKE", "LAST_PRICE", "BID", "ASK", "STATUS",
            "QTD_LAST", "VOL_BID", "VOL_ASK", "BOOK_HEADER",
            "HIGH", "LOW", "OPEN", "CLOSE", "VOLUME", "VOLUME_FIN",
        ]
        nomes = [m.name for m in FieldName]
        for e in expected:
            assert e in nomes, f"FieldName.{e} ausente"

    def test_profit_field_str_tem_book_header(self):
        assert FieldName.BOOK_HEADER in PROFIT_FIELD_STR
        assert PROFIT_FIELD_STR[FieldName.BOOK_HEADER] == "CAB"

    def test_profit_field_str_todos_campos_essenciais(self):
        obrigatorios = [
            FieldName.STRIKE, FieldName.LAST_PRICE, FieldName.BID,
            FieldName.ASK, FieldName.STATUS, FieldName.QTD_LAST,
            FieldName.VOL_BID, FieldName.VOL_ASK,
        ]
        for f in obrigatorios:
            assert f in PROFIT_FIELD_STR, f"Profit dict falta {f}"
            assert isinstance(PROFIT_FIELD_STR[f], str)
            assert len(PROFIT_FIELD_STR[f]) > 0

    def test_openfast_field_str_sem_book_header(self):
        assert FieldName.BOOK_HEADER not in OPENFAST_FIELD_STR

    def test_openfast_field_str_tem_strike(self):
        assert OPENFAST_FIELD_STR[FieldName.STRIKE] == "PEX"

    def test_openfast_field_str_ultimo_preco(self):
        assert OPENFAST_FIELD_STR[FieldName.LAST_PRICE] == "LAST"

    def test_market_data_source_e_protocol(self):
        assert hasattr(MarketDataSource, "__instancecheck__")

    def test_criar_data_source_default_retorna_rtd_adapter(self):
        source = criar_data_source("profit")
        from src.infrastructure.providers.rtd_profit_adapter import RTDProfitAdapter
        assert isinstance(source, RTDProfitAdapter)

    def test_criar_data_source_openfast_retorna_openfast(self):
        source = criar_data_source("openfast")
        from src.infrastructure.providers.openfast_socket_adapter import OpenFastSocketAdapter
        assert isinstance(source, OpenFastSocketAdapter)
        source.desconectar()

    def test_criar_data_source_fonte_desconhecida_avisa_warning(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="src.domain.services.market_data_source"):
            source = criar_data_source("openfsat")
        from src.infrastructure.providers.rtd_profit_adapter import RTDProfitAdapter
        assert isinstance(source, RTDProfitAdapter)
        assert any("openfsat" in r.message for r in caplog.records)
        assert any("caindo para RTD Profit" in r.message for r in caplog.records)
