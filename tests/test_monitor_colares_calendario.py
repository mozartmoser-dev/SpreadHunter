from src.application.use_cases.monitor_colares_calendario import (
    MonitorColaresCalendarioUseCase,
)


class TestCacheIvHistorico:
    def test_limpar_cache_iv_esvazia(self):
        uc = MonitorColaresCalendarioUseCase(db_path=None)
        uc._cache_iv_historico["PETR4"] = (0.1, 0.9, 0.5)
        uc.limpar_cache_iv()
        assert uc._cache_iv_historico == {}

    def test_recarregar_parametros_limpa_cache_iv(self):
        uc = MonitorColaresCalendarioUseCase(db_path=None)
        uc._cache_iv_historico["VALE3"] = (0.1, 0.9, 0.5)
        uc.recarregar_parametros()
        assert uc._cache_iv_historico == {}
