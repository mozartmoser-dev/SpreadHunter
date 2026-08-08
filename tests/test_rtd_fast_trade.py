import time
from unittest.mock import MagicMock

from src.infrastructure.providers.rtd_fast_trade import RTDFastTrade, _THROTTLE_DEFAULT_MS


def _ponte():
    rtd = RTDFastTrade()
    return rtd


class TestRTDFastTradeThrottle:
    def test_throttle_ms_configurável(self):
        rtd = RTDFastTrade(throttle_ms=120)
        assert rtd._throttle_ms == 120

    def test_throttle_zero_usa_default(self):
        rtd = RTDFastTrade(throttle_ms=0)
        assert rtd._throttle_ms == _THROTTLE_DEFAULT_MS


class TestRTDFastTradeRegistro:
    def test_registrar_topico_acumula_pendentes(self):
        rtd = _ponte()
        rtd.registrar_topico("PETR4", "PEX")
        assert "PETR4|PEX" in rtd._pendentes
        assert ("PETR4", "PEX") in rtd._subs

    def test_registrar_topico_campo_vazio_retorna_menos_um(self):
        rtd = _ponte()
        assert rtd.registrar_topico("PETR4", "") == -1

    def test_registrar_lista_conta(self):
        rtd = _ponte()
        n = rtd.registrar_lista([("PETR4", "PEX"), ("VALE3", "BID")])
        assert n == 2

    def test_registrar_status_usa_st(self):
        rtd = _ponte()
        rtd.registrar_status("PETR4")
        assert ("PETR4", "ST") in rtd._subs

    def test_campo_pendente_nao_duplica(self):
        rtd = _ponte()
        rtd.registrar_topico("PETR4", "BID")
        rtd.registrar_topico("PETR4", "BID")
        assert rtd._pendentes == {"PETR4|BID": "BID"}


class TestRTDFastTradeCache:
    def setup_method(self):
        self.rtd = RTDFastTrade()
        self.rtd._cache = {"PETR4|BID": 1.5}
        self.rtd._cache_ts = {"PETR4|BID": 10.0}

    def test_ler_campo_cache(self):
        assert self.rtd.ler_campo_cache("petr4", "bid") == 1.5

    def test_ler_campo_cache_upper_case(self):
        assert self.rtd.ler_campo_cache("PETR4", "BID") == 1.5

    def test_ler_campo_cache_zero_vira_zero(self):
        self.rtd._cache["PETR4|ASK"] = 0
        assert self.rtd.ler_campo_cache("PETR4", "ASK") == 0.0

    def test_ler_campo_cache_ausente_none(self):
        assert self.rtd.ler_campo_cache("PETR4", "ASK") is None

    def test_ler_status_cache(self):
        self.rtd._cache["PETR4|ST"] = "Aberto"
        assert self.rtd.ler_status_cache("petr4") == "ABERTO"

    def test_get_ts_campo(self):
        assert self.rtd.get_ts_campo("PETR4", "BID") == 10.0

    def test_get_idade_campo(self):
        self.rtd._cache_ts["PETR4|BID"] = time.time() - 2.0
        idade = self.rtd.get_idade_campo("PETR4", "BID")
        assert idade is not None and 1.5 <= idade <= 2.5

    def test_invalidar_cache(self):
        self.rtd.invalidar_cache("PETR4", "BID")
        assert "PETR4|BID" not in self.rtd._cache

    def test_desconectar_limpa_caches(self):
        self.rtd.desconectar()
        assert self.rtd._cache == {}
        assert self.rtd._cache_ts == {}
        assert self.rtd._pos == {}


class TestRTDFastTradeMatriz:
    def test_aplicar_pendentes_escreve_formulas(self):
        rtd = _ponte()
        rtd._ws = MagicMock()
        rtd.registrar_topico("PETR4", "PEX")
        rtd.registrar_topico("PETR4", "BID")
        rtd._aplicar_pendentes()
        assert rtd._pos == {"PETR4|PEX": (2, 1), "PETR4|BID": (2, 2)}
        assert "PETR4" in rtd._linha_por_cod

    def test_leitura_popula_cache_novamente(self):
        rtd = _ponte()
        rtd._ws = MagicMock()
        rtd._ws.Range.return_value.Value = ((25.0, 1050.0),)
        rtd.registrar_topico("PETR4", "PEX")
        rtd.registrar_topico("PETR4", "BID")
        rtd._aplicar_pendentes()
        rtd._ler_do_excel()
        assert rtd.ler_campo_cache("PETR4", "PEX") == 25.0
        assert rtd.ler_campo_cache("PETR4", "BID") == 1050.0

    def test_leitura_ignora_erro_excel(self):
        rtd = _ponte()
        rtd._ws = MagicMock()
        rtd._ws.Range.return_value.Value = (("#N/A", 1.0),)
        rtd.registrar_topico("PETR4", "PEX")
        rtd.registrar_topico("PETR4", "BID")
        rtd._aplicar_pendentes()
        rtd._ler_do_excel()
        assert rtd.ler_campo_cache("PETR4", "PEX") is None
        assert rtd.ler_campo_cache("PETR4", "BID") == 1.0

    def test_topico_usa_sqt_default(self):
        rtd = _ponte()
        assert rtd._topico_fn("PETR4") == ["SQT", "PETR4"]

    def test_sondar_topico_fallback(self):
        rtd = _ponte()
        rtd._ws = MagicMock()
        rtd._ws.Range.return_value.Value = None
        rtd._sondar_topico()
        assert rtd._topico_fn("PETR4") == ["SQT", "PETR4"]

    def test_refresh_sem_excel_tenta_abrir(self, monkeypatch):
        rtd = _ponte()
        monkeypatch.setattr(rtd, "_abrir", lambda: False)
        assert rtd.refresh(0) == {}