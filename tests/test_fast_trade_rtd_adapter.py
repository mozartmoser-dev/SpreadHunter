import time
from unittest.mock import MagicMock, patch

import pytest

from src.domain.services.market_data_source import FieldName
from src.infrastructure.providers.fast_trade_rtd_adapter import FastTradeRTDAdapter


@pytest.fixture
def adapter():
    """FastTradeRTDAdapter com RTDFastTrade mockado."""
    with patch("src.infrastructure.providers.fast_trade_rtd_adapter.RTDFastTrade") as mock:
        instance = mock.return_value
        instance.disponivel = True
        instance.registrar_topico.return_value = 0
        instance.registrar_status.return_value = 0
        instance.ler_campo_cache.return_value = 15.50
        instance.ler_status_cache.return_value = "Aberto"
        instance.forcar_leitura.return_value = 14.00
        instance.refresh.return_value = {}
        instance.reconectar.return_value = True
        instance.get_ts_campo.return_value = 123.45
        instance.get_idade_campo.return_value = 0.5
        yield FastTradeRTDAdapter()


class TestFastTradeRTDAdapter:
    def test_suporta_push_false(self, adapter):
        assert adapter.suporta_push is False

    def test_suporta_cab_skip_true(self, adapter):
        assert adapter.suporta_cab_skip is True

    def test_disponivel_delega(self, adapter):
        assert adapter.disponivel is True

    def test_registrar_topico_traduz_strike(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.STRIKE)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "PEX")

    def test_registrar_topico_traduz_bid(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.BID)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "BID")

    def test_registrar_topico_traduz_ask(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.ASK)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "ASK")

    def test_registrar_topico_traduz_book_header(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.BOOK_HEADER)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "CAB")

    def test_registrar_topico_traduz_status(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.STATUS)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "ST")

    def test_registrar_status_delega(self, adapter):
        adapter.registrar_status("PETR4")
        adapter._rtd.registrar_status.assert_called_once_with("PETR4")

    def test_ler_campo_cache_traduz_last_price(self, adapter):
        v = adapter.ler_campo_cache("PETR4", FieldName.LAST_PRICE)
        adapter._rtd.ler_campo_cache.assert_called_once_with("PETR4", "LAST")
        assert v == 15.50

    def test_ler_campos_agrupa(self, adapter):
        r = adapter.ler_campos("PETR4", FieldName.BID, FieldName.ASK)
        assert r == {FieldName.BID: 15.50, FieldName.ASK: 15.50}

    def test_ler_status_cache_delega(self, adapter):
        assert adapter.ler_status_cache("PETR4") == "Aberto"

    def test_forcar_leitura_traduz_ask(self, adapter):
        v = adapter.forcar_leitura("PETR4", FieldName.ASK)
        adapter._rtd.forcar_leitura.assert_called_once_with("PETR4", "ASK")
        assert v == 14.00

    def test_refresh_delega(self, adapter):
        result = adapter.refresh(5000)
        adapter._rtd.refresh.assert_called_once_with(5000)

    def test_reconectar_delega(self, adapter):
        assert adapter.reconectar() is True
        adapter._rtd.reconectar.assert_called_once()

    def test_desconectar_delega(self, adapter):
        adapter.desconectar()
        adapter._rtd.desconectar.assert_called_once()

    def test_invalidar_cache_traduz_strike(self, adapter):
        adapter.invalidar_cache("PETR4", FieldName.STRIKE)
        adapter._rtd.invalidar_cache.assert_called_once_with("PETR4", "PEX")

    def test_get_ts_campo_delega(self, adapter):
        ts = adapter.get_ts_campo("PETR4", FieldName.ASK)
        adapter._rtd.get_ts_campo.assert_called_once_with("PETR4", "ASK")
        assert ts == 123.45

    def test_get_idade_campo_delega(self, adapter):
        idade = adapter.get_idade_campo("PETR4", FieldName.ASK)
        adapter._rtd.get_idade_campo.assert_called_once_with("PETR4", "ASK")
        assert idade == 0.5

    def test_resolver_com_str_passa_direto(self, adapter):
        assert adapter._resolver("CAMPO_QUALQUER") == "CAMPO_QUALQUER"

    def test_resolver_com_field_name_sem_mapeamento_retorna_vazio(self, adapter):
        assert adapter._resolver("NAO_EXISTE") == "NAO_EXISTE"


class TestFastTradeRTDAdapterThrottle:
    def test_throttle_ms_repassado_a_ponte(self):
        with patch("src.infrastructure.providers.fast_trade_rtd_adapter.RTDFastTrade") as mock:
            FastTradeRTDAdapter(throttle_ms=120)
            mock.assert_called_once_with(throttle_ms=120)

    def test_throttle_default_200(self):
        with patch("src.infrastructure.providers.fast_trade_rtd_adapter.RTDFastTrade") as mock:
            FastTradeRTDAdapter()
            mock.assert_called_once_with(throttle_ms=200)
