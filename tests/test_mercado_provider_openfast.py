import time
import pytest
from datetime import date, timedelta

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.market_data_source import FieldName
from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider
from src.infrastructure.providers.openfast_socket_adapter import OpenFastSocketAdapter
from tests.helpers.mock_fast_trade_server import MockFastTradeServer

PORT = 5558
HOST = "127.0.0.1"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test_mercado_provider_openfast.db"
    conn = init_db(path)
    conn.close()
    ParametroRepository(path).seed_defaults()
    return path


@pytest.fixture
def populated_db(db_path):
    repo = InstrumentoRepository(db_path)
    venc = date.today() + timedelta(days=30)
    for strike in [12.4, 15.0, 18.0]:
        s = int(strike * 10)
        repo.save(InstrumentoOpcional(
            ativo="PETR4",
            cod_put=f"PETRG{s}",
            cod_call=f"PETRH{s}",
            vencimento=venc,
            tipo_opcao=TipoOpcao.AMERICANA,
        ))
    return db_path


@pytest.fixture
def server():
    s = MockFastTradeServer(host=HOST, port=PORT)
    s.start()
    yield s
    s.stop()


class TestMercadoProviderOpenFast:

    def test_cria_com_adapter(self, populated_db, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            provider = MercadoDataProvider(populated_db, adapter)
            assert provider.source is adapter
            assert provider.source.disponivel is True
            assert provider.source.suporta_push is True
            assert provider.source.suporta_cab_skip is False
        finally:
            adapter.desconectar()

    def test_onda1_registra_instrumentos(self, populated_db, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            provider = MercadoDataProvider(populated_db, adapter)
            result = provider.capturar_dados_mercado()
            assert provider._registrado is True
        finally:
            adapter.desconectar()

    def test_capturar_com_dados_push(self, populated_db, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            # Push dados do ativo
            server.push("PETR4", "LAST", "28.50")
            server.push("PETR4", "BID", "28.45")
            server.push("PETR4", "ASK", "28.55")
            time.sleep(0.15)

            # Registro Onda 1
            provider = MercadoDataProvider(populated_db, adapter)
            provider.capturar_dados_mercado()

            # Força manutenção para detectar books
            server.push("PETRG180", "ASK", "0.85")
            server.push("PETRH180", "BID", "0.75")
            server.push("PETRG180", "BID", "0.80")
            server.push("PETRH180", "ASK", "0.78")
            server.push("PETRG180", "ST", "A")
            server.push("PETRH180", "ST", "A")
            server.push("PETR4", "ST", "A")
            time.sleep(0.15)

            provider.fazer_manutencao()
            assert len(provider._chaves_com_book) > 0

            dados = provider.capturar_dados_mercado()
            assert isinstance(dados, dict)
        finally:
            adapter.desconectar()

    def test_cab_skip_desabilitado(self, populated_db, server):
        """Open Fast nao usa CAB skip — suporta_cab_skip=False."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            provider = MercadoDataProvider(populated_db, adapter)
            assert adapter.suporta_cab_skip is False
            assert adapter.suporta_push is True
        finally:
            adapter.desconectar()

    def test_recarregar_parametros(self, populated_db, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            provider = MercadoDataProvider(populated_db, adapter)
            provider.recarregar_parametros()
            assert provider._carga_inteligente_habilitada is False
        finally:
            adapter.desconectar()

    def test_get_engine_stats(self, populated_db, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            provider = MercadoDataProvider(populated_db, adapter)
            provider.capturar_dados_mercado()
            stats = provider.get_engine_stats()
            assert "total" in stats
            assert "onda1" in stats
            assert "onda2" in stats
        finally:
            adapter.desconectar()

    def test_invalidar_cache_no_openfast(self, populated_db, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            server.push("PETR4", "LAST", "28.50")
            time.sleep(0.1)
            v = adapter.ler_campo_cache("PETR4", FieldName.LAST_PRICE)
            assert v == 28.50

            adapter.invalidar_cache("PETR4", FieldName.LAST_PRICE)
            v2 = adapter.ler_campo_cache("PETR4", FieldName.LAST_PRICE)
            assert v2 is None
        finally:
            adapter.desconectar()

    def test_perna_stale_nao_alimenta_e_retoma_com_push_novo(self, populated_db, server):
        """E2E: book fresco gera; após a janela de frescor (sem push novo) a perna
        fica STALE e NÃO alimenta; novo push verdadeiro retoma a geração."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001,
                                        stale_campo_s=1.0)
        try:
            def sobe():
                server.push("PETR4", "LAST", "28.50")
                server.push("PETR4", "BID", "28.45")
                server.push("PETR4", "ASK", "28.55")
                server.push("PETR4", "ST", "A")
                server.push("PETRG180", "PEX", "18.0")
                server.push("PETRH180", "PEX", "18.0")
                server.push("PETRG180", "ASK", "0.85")
                server.push("PETRG180", "BID", "0.80")
                server.push("PETRG180", "ST", "A")
                server.push("PETRH180", "ASK", "0.78")
                server.push("PETRH180", "BID", "0.75")
                server.push("PETRH180", "ST", "A")

            sobe()
            time.sleep(0.15)

            provider = MercadoDataProvider(populated_db, adapter)
            provider.capturar_dados_mercado()
            provider.fazer_manutencao()
            assert len(provider._chaves_com_book) > 0

            # 1) Dados frescos -> entrada gerada e sem contagem de skip
            sobe()
            time.sleep(0.15)
            d1 = provider.capturar_dados_mercado()
            fresh_keys = [k for k in d1 if k.startswith("PETR4|")]
            assert len(fresh_keys) > 0, "book fresco deveria gerar entry"
            skip_antes = provider._cont_stale_skip

            # 2) Envelhece a janela de frescor (sem push novo) -> STALE skip
            time.sleep(1.3)
            d2 = provider.capturar_dados_mercado()
            stale_keys = [k for k in d2 if k.startswith("PETR4|")]
            assert provider._cont_stale_skip > skip_antes
            assert len(stale_keys) == 0, "perna stale não pode alimentar d2"

            # 3) Novo push verdadeiro -> freshness volta a gerar
            server.push("PETR4", "PEX", "28.50")
            server.push("PETR4", "BID", "28.44")
            server.push("PETR4", "ASK", "28.56")
            server.push("PETRG180", "PEX", "18.0")
            server.push("PETRH180", "PEX", "18.0")
            server.push("PETRG180", "ASK", "0.86")
            server.push("PETRG180", "BID", "0.81")
            server.push("PETRH180", "ASK", "0.77")
            server.push("PETRH180", "BID", "0.74")
            time.sleep(0.15)
            d3 = provider.capturar_dados_mercado()
            retomou_keys = [k for k in d3 if k.startswith("PETR4|")]
            assert len(retomou_keys) > 0, "push novo deve retomar geração"
        finally:
            adapter.desconectar()
