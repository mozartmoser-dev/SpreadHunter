import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from src.domain.services.market_data_source import FieldName
from src.infrastructure.providers.rtd_profit_adapter import RTDProfitAdapter


@pytest.fixture
def adapter():
    """RTDProfitAdapter com RTDProfit mockado."""
    with patch("src.infrastructure.providers.rtd_profit_adapter.RTDProfit") as mock:
        instance = mock.return_value
        instance.disponivel = True
        instance.registrar_topico.return_value = 42
        instance.registrar_status.return_value = 43
        instance.ler_campo_cache.return_value = 15.50
        instance.ler_status_cache.return_value = "Aberto"
        instance.forcar_leitura.return_value = 14.00
        instance.refresh.return_value = {"PETR4|ULT": 15.50}
        instance.reconectar.return_value = True
        yield RTDProfitAdapter()


class TestRTDProfitAdapter:
    def test_suporta_push_false(self, adapter):
        assert adapter.suporta_push is False

    def test_suporta_cab_skip_true(self, adapter):
        assert adapter.suporta_cab_skip is True

    def test_disponivel_delega(self, adapter):
        assert adapter.disponivel is True

    def test_registrar_topico_traduz_strike(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.STRIKE)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "PEX")

    def test_registrar_topico_traduz_last_price(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.LAST_PRICE)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "ULT")

    def test_registrar_topico_traduz_bid(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.BID)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "OCP")

    def test_registrar_topico_traduz_ask(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.ASK)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "OVD")

    def test_registrar_topico_traduz_book_header(self, adapter):
        adapter.registrar_topico("PETR4", FieldName.BOOK_HEADER)
        adapter._rtd.registrar_topico.assert_called_once_with("PETR4", "CAB")

    def test_registrar_status_delega(self, adapter):
        tid = adapter.registrar_status("PETR4")
        adapter._rtd.registrar_status.assert_called_once_with("PETR4")
        assert tid == 43

    def test_ler_campo_cache_traduz_strike(self, adapter):
        v = adapter.ler_campo_cache("PETR4", FieldName.STRIKE)
        adapter._rtd.ler_campo_cache.assert_called_once_with("PETR4", "PEX")
        assert v == 15.50

    def test_ler_campo_cache_traduz_last_price(self, adapter):
        v = adapter.ler_campo_cache("PETR4", FieldName.LAST_PRICE)
        adapter._rtd.ler_campo_cache.assert_called_once_with("PETR4", "ULT")
        assert v == 15.50

    def test_ler_status_cache_delega(self, adapter):
        v = adapter.ler_status_cache("PETR4")
        adapter._rtd.ler_status_cache.assert_called_once_with("PETR4")
        assert v == "Aberto"

    def test_forcar_leitura_traduz_bid(self, adapter):
        v = adapter.forcar_leitura("PETR4", FieldName.BID)
        adapter._rtd.forcar_leitura.assert_called_once_with("PETR4", "OCP")
        assert v == 14.00

    def test_refresh_delega(self, adapter):
        result = adapter.refresh(5000)
        adapter._rtd.refresh.assert_called_once_with(5000)
        assert result == {"PETR4|ULT": 15.50}

    def test_reconectar_delega(self, adapter):
        assert adapter.reconectar() is True
        adapter._rtd.reconectar.assert_called_once()

    def test_desconectar_delega(self, adapter):
        adapter.desconectar()
        adapter._rtd.desconectar.assert_called_once()

    def test_resolver_com_str_passa_direto(self, adapter):
        result = adapter._resolver("CAMPO_QUALQUER")
        assert result == "CAMPO_QUALQUER"

    def test_resolver_com_field_name_sem_mapeamento_retorna_vazio(self, adapter):
        """HIGH existe no enum mas nao no PROFIT_FIELD_STR (so Open Fast)."""
        result = adapter._resolver(FieldName.HIGH)
        assert result == ""
