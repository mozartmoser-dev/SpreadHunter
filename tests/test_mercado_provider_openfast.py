import time
import pytest
from datetime import date, timedelta

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.entities.parametro_operacional import ParametroOperacional
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

    def test_feed_push_sem_push_continua_alimentando_e_novo_push_atualiza(self, populated_db, server):
        """E2E: book fresco gera; para feed push change-driven, a ausência de push
        NÃO é stale (sem push = cotação não mudou = atual). O valor presente
        continua alimentando as calculadoras mesmo após a janela de idade; um
        novo push verdadeiro atualiza os valores."""
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

            # 2) O valor envelhece além da janela SEM push novo -> segue gerando
            #    (não houve mudança => cotação atual; allow_stale para push)
            time.sleep(1.3)
            d2 = provider.capturar_dados_mercado()
            still_keys = [k for k in d2 if k.startswith("PETR4|")]
            assert len(still_keys) > 0, "ausência de push não pode bloquear a geração"
            assert provider._cont_stale_skip == skip_antes, "não deve haver skip por idade no feed push"

            # 3) Novo push verdadeiro -> valores atualizados continuam a gerar
            server.push("PETR4", "BID", "28.44")
            server.push("PETR4", "ASK", "28.56")
            server.push("PETRG180", "ASK", "0.86")
            server.push("PETRG180", "BID", "0.81")
            server.push("PETRH180", "ASK", "0.77")
            server.push("PETRH180", "BID", "0.74")
            time.sleep(0.15)
            d3 = provider.capturar_dados_mercado()
            retomou_keys = [k for k in d3 if k.startswith("PETR4|")]
            assert len(retomou_keys) > 0, "push novo deve continuar gerando"
        finally:
            adapter.desconectar()

    def test_assinar_timestamp_openfast_desabilitado_por_default(self, populated_db, server):
        """Parâmetro desligado (default) não assina TIME/TIMENEG do ativo."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            provider = MercadoDataProvider(populated_db, adapter)
            provider.capturar_dados_mercado()
            subscricoes = {c for _, c in adapter._subscriptions}
            assert "TIME" not in subscricoes
            assert "TIMENEG" not in subscricoes
        finally:
            adapter.desconectar()

    def test_assinar_timestamp_openfast_habilitado_assina_campos(self, populated_db, server):
        """Com parâmetro ativo, o provider assina TIME/TIMENEG do ativo."""
        ParametroRepository(populated_db).save(ParametroOperacional(
            chave="assinar_timestamp_openfast", valor=1.0,
            estrategia="GERAL", descricao="teste"))
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            provider = MercadoDataProvider(populated_db, adapter)
            provider.recarregar_parametros()
            provider.capturar_dados_mercado()
            subscricoes = {c for _, c in adapter._subscriptions}
            assert "TIME" in subscricoes
            assert "TIMENEG" in subscricoes
        finally:
            adapter.desconectar()

    def test_anota_origem_no_entry(self, populated_db, server):
        """Com timestamp assinado e push de TIME/TIMENEG, o entry carrega
        ts_origem_ativo/idade_origem_ativo (diagnóstico, sem tocar _cache_ts)."""
        ParametroRepository(populated_db).save(ParametroOperacional(
            chave="assinar_timestamp_openfast", valor=1.0,
            estrategia="GERAL", descricao="teste"))
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            provider = MercadoDataProvider(populated_db, adapter)
            provider.recarregar_parametros()

            agora = time.time()
            server.push("PETR4", "LAST", "28.50")
            server.push("PETR4", "BID", "28.45")
            server.push("PETR4", "ASK", "28.55")
            server.push("PETR4", "ST", "A")
            server.push("PETR4", "TIMENEG", f"{agora - 2.0:.3f}")
            server.push("PETR4", "TIME", f"{agora - 1.0:.3f}")
            server.push("PETRG180", "PEX", "18.0")
            server.push("PETRH180", "PEX", "18.0")
            server.push("PETRG180", "ASK", "0.85")
            server.push("PETRG180", "BID", "0.80")
            server.push("PETRG180", "ST", "A")
            server.push("PETRH180", "ASK", "0.78")
            server.push("PETRH180", "BID", "0.75")
            server.push("PETRH180", "ST", "A")
            time.sleep(0.2)

            provider.capturar_dados_mercado()
            provider.fazer_manutencao()
            dados = provider.capturar_dados_mercado()
            entries = [e for e in dados.values() if isinstance(e, dict) and e.get("ts_origem_ativo")]
            assert entries, "entry deveria carregar ts_origem_ativo com timestamp assinado"
            for e in entries:
                assert e.get("ts_origem_ativo") is not None
                assert e.get("idade_origem_ativo") is not None
                assert e.get("ts_origem_ativo") > 1_000_000_000
        finally:
            adapter.desconectar()

    def test_anota_time_timeng_no_entry(self, populated_db, server):
        """TIME/TIMENEG do OpenFast viram ts_time_ativo/ts_timeng_ativo no entry."""
        ParametroRepository(populated_db).save(ParametroOperacional(
            chave="assinar_timestamp_openfast", valor=1.0,
            estrategia="GERAL", descricao="teste"))
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        try:
            provider = MercadoDataProvider(populated_db, adapter)
            provider.recarregar_parametros()

            agora = time.time()
            server.push("PETR4", "LAST", "28.50")
            server.push("PETR4", "BID", "28.45")
            server.push("PETR4", "ASK", "28.55")
            server.push("PETR4", "ST", "A")
            server.push("PETR4", "TIMENEG", f"{agora - 2.0:.3f}")
            server.push("PETR4", "TIME", f"{agora - 1.0:.3f}")
            server.push("PETRG180", "PEX", "18.0")
            server.push("PETRH180", "PEX", "18.0")
            server.push("PETRG180", "ASK", "0.85")
            server.push("PETRG180", "BID", "0.80")
            server.push("PETRG180", "ST", "A")
            server.push("PETRH180", "ASK", "0.78")
            server.push("PETRH180", "BID", "0.75")
            server.push("PETRH180", "ST", "A")
            time.sleep(0.2)

            provider.capturar_dados_mercado()
            provider.fazer_manutencao()
            dados = provider.capturar_dados_mercado()
            entries = [e for e in dados.values() if isinstance(e, dict) and e.get("ts_time_ativo")]
            assert entries, "entry deveria carregar ts_time_ativo com timestamp assinado"
            for e in entries:
                assert e.get("ts_time_ativo") is not None
                assert e.get("ts_timeng_ativo") is not None
                assert e.get("ts_time_ativo") > 1_000_000_000
                # TIME vem ~1s depois de TIMENEG na simulação
                assert e.get("ts_time_ativo") > e.get("ts_timeng_ativo")
        finally:
            adapter.desconectar()
