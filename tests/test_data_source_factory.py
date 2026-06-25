import pytest
from src.domain.services.market_data_source import criar_data_source


class TestDataSourceFactory:
    def test_factory_retorna_rtd_adapter_para_profit(self):
        from src.infrastructure.providers.rtd_profit_adapter import RTDProfitAdapter
        source = criar_data_source("profit")
        assert isinstance(source, RTDProfitAdapter)

    def test_factory_retorna_openfast_para_openfast(self):
        from src.infrastructure.providers.openfast_socket_adapter import OpenFastSocketAdapter
        source = criar_data_source("openfast")
        assert isinstance(source, OpenFastSocketAdapter)
        source.desconectar()

    def test_factory_retorna_rtd_adapter_para_qualquer_outro(self):
        from src.infrastructure.providers.rtd_profit_adapter import RTDProfitAdapter
        source = criar_data_source("qualquer_coisa")
        assert isinstance(source, RTDProfitAdapter)

    def test_factory_openfast_tem_suporta_push_true(self):
        source = criar_data_source("openfast")
        assert source.suporta_push is True
        source.desconectar()

    def test_factory_profit_tem_suporta_push_false(self):
        source = criar_data_source("profit")
        assert source.suporta_push is False

    def test_factory_openfast_suporta_cab_skip_false(self):
        source = criar_data_source("openfast")
        assert source.suporta_cab_skip is False
        source.desconectar()

    def test_factory_profit_suporta_cab_skip_true(self):
        source = criar_data_source("profit")
        assert source.suporta_cab_skip is True
