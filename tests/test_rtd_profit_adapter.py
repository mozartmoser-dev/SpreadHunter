import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import threading

from src.domain.services.market_data_source import FieldName
from src.infrastructure.providers.rtd_profit_adapter import RTDProfitAdapter
from src.infrastructure.providers.rtd_profit import RTDProfit


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


def _rtd_sem_com():
    """RTDProfit sem conexão COM: só os mapas internos usados por ler_campo_cache."""
    rtd = RTDProfit.__new__(RTDProfit)
    rtd._lock = threading.Lock()
    rtd._topic_map = {"PETR4|ULT": 42}
    rtd._valores = {42: "25.50"}
    return rtd


class TestRTDProfitNormalizacaoNegativo:
    def test_valor_positivo_retorna_valor(self):
        rtd = _rtd_sem_com()
        assert rtd.ler_campo_cache("PETR4", "ULT") == 25.50

    def test_valor_zero_retorna_zero(self):
        rtd = _rtd_sem_com()
        rtd._valores = {42: "0"}
        assert rtd.ler_campo_cache("PETR4", "ULT") == 0.0

    def test_negativo_vira_none_e_nao_zero(self):
        """Regressão: negativo deve virar None. Antes virava 0.0 e sobrescrevia
        um book válido anterior com falso zero no provider."""
        rtd = _rtd_sem_com()
        rtd._valores = {42: "-1.50"}
        assert rtd.ler_campo_cache("PETR4", "ULT") is None

    def test_negativo_nao_sobrescreve_valor_anterior(self):
        rtd = _rtd_sem_com()
        assert rtd.ler_campo_cache("PETR4", "ULT") == 25.50
        rtd._valores = {42: "-1.50"}
        assert rtd.ler_campo_cache("PETR4", "ULT") is None
