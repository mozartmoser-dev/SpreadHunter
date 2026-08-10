import time
import pytest

from src.domain.services.market_data_source import FieldName
from src.infrastructure.providers.openfast_socket_adapter import OpenFastSocketAdapter
from tests.helpers.mock_fast_trade_server import MockFastTradeServer

PORT = 5557
HOST = "127.0.0.1"


@pytest.fixture
def server():
    s = MockFastTradeServer(host=HOST, port=PORT)
    s.start()
    yield s
    s.stop()


class TestOpenFastSocketAdapterConecta:
    def test_conecta_e_handshake(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        assert adapter._conectado is True
        assert adapter._ultimo_syn > 0
        adapter.desconectar()

    def test_disponivel_apos_conexao(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        assert adapter.disponivel is True
        adapter.desconectar()

    def test_suporta_push_true(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        assert adapter.suporta_push is True
        adapter.desconectar()

    def test_suporta_cab_skip_false(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        assert adapter.suporta_cab_skip is False
        adapter.desconectar()


class TestOpenFastSocketAdapterCache:
    def test_ler_campo_cache_retorna_none_sem_dado(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        v = adapter.ler_campo_cache("PETR4", FieldName.LAST_PRICE)
        assert v is None
        adapter.desconectar()

    def test_recebe_push_e_le_cache(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "LAST", "25.50")
        time.sleep(0.1)
        v = adapter.ler_campo_cache("PETR4", FieldName.LAST_PRICE)
        assert v == 25.50
        adapter.desconectar()

    def test_recebe_push_strike(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "PEX", "28.00")
        time.sleep(0.1)
        v = adapter.ler_campo_cache("PETR4", FieldName.STRIKE)
        assert v == 28.00
        adapter.desconectar()

    def test_recebe_push_bid(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "BID", "1.23")
        time.sleep(0.1)
        v = adapter.ler_campo_cache("PETR4", FieldName.BID)
        assert v == 1.23
        adapter.desconectar()

    def test_recebe_push_ask(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "ASK", "1.25")
        time.sleep(0.1)
        v = adapter.ler_campo_cache("PETR4", FieldName.ASK)
        assert v == 1.25
        adapter.desconectar()

    def test_valor_com_virgula(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "LAST", "25,50")
        time.sleep(0.1)
        v = adapter.ler_campo_cache("PETR4", FieldName.LAST_PRICE)
        assert v == 25.50
        adapter.desconectar()

    def test_valor_zero_retorna_zero(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "LAST", "0")
        time.sleep(0.1)
        v = adapter.ler_campo_cache("PETR4", FieldName.LAST_PRICE)
        assert v == 0.0
        adapter.desconectar()

    def test_ler_status_cache_aberto(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "ST", "A")
        time.sleep(0.1)
        v = adapter.ler_status_cache("PETR4")
        assert v == "Aberto"
        adapter.desconectar()

    def test_ler_status_cache_leilao(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "ST", "L")
        time.sleep(0.1)
        v = adapter.ler_status_cache("PETR4")
        assert v == "Leilão"
        adapter.desconectar()

    def test_ler_status_cache_fechado(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "ST", "F")
        time.sleep(0.1)
        v = adapter.ler_status_cache("PETR4")
        assert v == "Fechado"
        adapter.desconectar()

    def test_ler_status_cache_aberto_por_extenso(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "ST", "ABERTO")
        time.sleep(0.1)
        v = adapter.ler_status_cache("PETR4")
        assert v == "Aberto"
        adapter.desconectar()

    def test_ler_status_cache_vazio_se_sem_dado(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        v = adapter.ler_status_cache("PETR4")
        assert v == ""
        adapter.desconectar()


class TestOpenFastSocketAdapterDirtyKeys:
    def test_refresh_retorna_mudancas(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "LAST", "25.50")
        server.push("VALE3", "BID", "10.10")
        time.sleep(0.1)
        mudancas = adapter.refresh()
        assert "PETR4|LAST" in mudancas
        assert "VALE3|BID" in mudancas
        assert mudancas["PETR4|LAST"] == 25.50
        adapter.desconectar()

    def test_refresh_limpa_dirty_keys(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "LAST", "25.50")
        time.sleep(0.1)
        adapter.refresh()
        mudancas2 = adapter.refresh()
        assert len(mudancas2) == 0
        adapter.desconectar()

    def test_cache_persiste_apos_refresh(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "LAST", "25.50")
        time.sleep(0.1)
        adapter.refresh()
        v = adapter.ler_campo_cache("PETR4", FieldName.LAST_PRICE)
        assert v == 25.50
        adapter.desconectar()


class TestOpenFastSocketAdapterSync:
    def test_syn_mantem_disponivel(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.send_syn()
        time.sleep(0.05)
        assert adapter.disponivel is True
        adapter.desconectar()

    def test_syn_nao_renova_idade_ask_bid(self, server):
        """Heartbeat NÃO atualiza _cache_ts de ASK/BID: com janela curta o campo
        fica STALE mesmo com SYN chegando — e não renova o timestamp."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001,
                                        stale_campo_s=0.2)
        server.push("PETR4", "ASK", "1.25")
        time.sleep(0.05)
        assert adapter.ler_campo_cache("PETR4", FieldName.ASK) == 1.25
        ts_antes = adapter.get_ts_campo("PETR4", FieldName.ASK)
        server.send_syn()
        server.send_syn()
        time.sleep(0.05)
        ts_depois = adapter.get_ts_campo("PETR4", FieldName.ASK)
        assert ts_depois == ts_antes
        time.sleep(0.35)
        server.send_syn()
        assert adapter.is_stale_campo("PETR4", FieldName.ASK) is True
        assert adapter.ler_campo_cache("PETR4", FieldName.ASK) is None
        adapter.desconectar()


class TestOpenFastSocketAdapterRegistrar:
    def test_registrar_topico_bid(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        rc = adapter.registrar_topico("PETR4", FieldName.BID)
        assert rc == 0
        time.sleep(0.05)
        assert ("PETR4", "BID") in adapter._subscriptions
        adapter.desconectar()

    def test_registrar_topico_desconhecido_retorna_menos1(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        rc = adapter.registrar_topico("PETR4", FieldName.BOOK_HEADER)
        assert rc == -1
        adapter.desconectar()

    def test_registrar_status(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        rc = adapter.registrar_status("PETR4")
        assert rc == 0
        adapter.desconectar()

    def test_forcar_leitura_aguarda_evento_novo(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        import threading
        def push_depois():
            time.sleep(0.1)
            server.push("PETR4", "BID", "1.23")
        t = threading.Thread(target=push_depois, daemon=True)
        t.start()
        v = adapter.forcar_leitura("PETR4", FieldName.BID)
        assert v == 1.23
        adapter.desconectar()

    def test_forcar_leitura_sem_evento_novo_retorna_none(self, server):
        """Evento anterior à chamada NÃO conta — sem push novo deve retornar None."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "BID", "1.23")
        time.sleep(0.1)
        v = adapter.forcar_leitura("PETR4", FieldName.BID, timeout_ms=200)
        assert v is None
        adapter.desconectar()

    def test_forcar_leitura_evento_novo_permite_allow_stale(self, server):
        """Com allow_stale=True devolve mesmo sem push novo (valor em cache)."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "BID", "1.23")
        time.sleep(0.1)
        v = adapter.forcar_leitura("PETR4", FieldName.BID, allow_stale=True,
                                   timeout_ms=200)
        assert v == 1.23
        adapter.desconectar()


class TestOpenFastSocketAdapterSeparador:
    def test_parse_linha_com_hash(self, server):
        """Adapter tambem aceita # como separador."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        result = adapter._parse_linha("SQT#PETR4#LAST#30.00")
        assert result is not None
        chave, valor = result
        assert chave == ("PETR4", "LAST")
        assert valor == 30.00
        adapter.desconectar()

    def test_ignora_linha_invalida(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        assert adapter._parse_linha("LIXO") is None
        assert adapter._parse_linha("") is None  # nao deve crashar
        adapter.desconectar()

    def test_ignora_sqt_com_poucas_partes(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        assert adapter._parse_linha("SQT#PETR4") is None  # < 4 partes
        adapter.desconectar()


class TestOpenFastSocketAdapterReconexao:
    def test_reconectar(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        assert adapter.reconectar() is True
        assert adapter._conectado is True
        adapter.desconectar()

    def test_disponivel_falso_apos_desconectar(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        adapter.desconectar()
        assert adapter.disponivel is False


class TestOpenFastSocketAdapterStale:
    def test_ler_campo_cache_stale_retorna_none_allow_false(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001,
                                        stale_campo_s=0.2)
        server.push("PETR4", "ASK", "1.25")
        time.sleep(0.05)
        assert adapter.ler_campo_cache("PETR4", FieldName.ASK) == 1.25
        time.sleep(0.25)
        assert adapter.ler_campo_cache("PETR4", FieldName.ASK) is None
        adapter.desconectar()

    def test_ler_campo_cache_allow_stale_true_retorna_valor_antigo(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001,
                                        stale_campo_s=0.2)
        server.push("PETR4", "ASK", "1.25")
        time.sleep(0.05)
        time.sleep(0.35)
        assert adapter.ler_campo_cache("PETR4", FieldName.ASK, allow_stale=True) == 1.25
        adapter.desconectar()

    def test_is_stale_campo(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001,
                                        stale_campo_s=0.2)
        server.push("PETR4", "ASK", "1.25")
        time.sleep(0.05)
        assert adapter.is_stale_campo("PETR4", FieldName.ASK) is False
        time.sleep(0.35)
        assert adapter.is_stale_campo("PETR4", FieldName.ASK) is True
        adapter.desconectar()

    def test_ler_campos_allow_stale_respeita_janela(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001,
                                        stale_campo_s=0.2)
        server.push("PETR4", "ASK", "1.25")
        server.push("PETR4", "BID", "1.20")
        time.sleep(0.05)
        campos = adapter.ler_campos("PETR4", FieldName.ASK, FieldName.BID)
        assert campos[FieldName.ASK] == 1.25
        assert campos[FieldName.BID] == 1.20
        time.sleep(0.35)
        assert adapter.ler_campos("PETR4", FieldName.ASK, FieldName.BID)[FieldName.ASK] is None
        adapter.desconectar()


class TestOpenFastSocketAdapterWatchdog:
    def test_thread_morta_marca_desconectado(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        assert adapter._conectado is True
        adapter._reader_thread = None
        st = adapter.verificar_conexao()
        assert st == "desconectado"
        assert adapter._conectado is False
        adapter.desconectar()

    def test_thread_morta_invalida_cache(self, server):
        """Thread morta -> DISCONNECTED e cache invalidado (nada ressuscita)."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "ASK", "1.25")
        time.sleep(0.1)
        assert adapter.ler_campo_cache("PETR4", FieldName.ASK, allow_stale=True) == 1.25
        adapter._reader_thread = None
        adapter.verificar_conexao()
        assert adapter._cache == {}
        assert adapter._cache_ts == {}
        assert adapter._cache_ver == {}
        assert adapter.ler_campo_cache("PETR4", FieldName.ASK, allow_stale=True) is None
        adapter.desconectar()


class TestOpenFastSocketAdapterReconexaoGeneracao:
    def test_reconectar_incrementa_subscription_generation(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        gen0 = adapter._subscription_generation
        assert gen0 == 1
        assert adapter.reconectar() is True
        assert adapter._subscription_generation == gen0 + 1
        adapter.desconectar()

    def test_reconexao_nao_ressuscita_dados_antigos(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "ASK", "1.25")
        time.sleep(0.1)
        assert adapter.ler_campo_cache("PETR4", FieldName.ASK, allow_stale=True) == 1.25
        adapter.desconectar()
        assert adapter._cache == {}
        assert adapter.reconectar() is True
        assert adapter.ler_campo_cache("PETR4", FieldName.ASK, allow_stale=True) is None
        adapter.desconectar()


class TestOpenFastSocketAdapterOrigem:
    def test_get_ts_origem_none_sem_dado(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        assert adapter.get_ts_origem("PETR4") is None
        assert adapter.get_idade_origem("PETR4") is None
        adapter.desconectar()

    def test_get_ts_origem_prefere_timeneg(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "TIME", "1700000000.000")
        server.push("PETR4", "TIMENEG", "1700000100.500")
        time.sleep(0.1)
        assert adapter.get_ts_origem("PETR4") == 1700000100.5
        adapter.desconectar()

    def test_get_ts_origem_fallback_time(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "TIME", "1700000200.000")
        time.sleep(0.1)
        assert adapter.get_ts_origem("PETR4") == 1700000200.0
        adapter.desconectar()

    def test_get_ts_origem_ignora_zero(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "TIMENEG", "0")
        server.push("PETR4", "TIME", "1700000300.000")
        time.sleep(0.1)
        assert adapter.get_ts_origem("PETR4") == 1700000300.0
        adapter.desconectar()

    def test_get_ts_origem_aceita_virgula(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "TIMENEG", "1700000400,500")
        time.sleep(0.1)
        assert adapter.get_ts_origem("PETR4") == 1700000400.5
        adapter.desconectar()

    def test_get_idade_origem_valida_escala_absoluta(self, server):
        """Valor fora de escala de time.time() -> None (não é timestamp absoluto)."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "TIMENEG", "150")  # hora HHMMSS, não é epoch
        time.sleep(0.1)
        assert adapter.get_ts_origem("PETR4") == 150.0
        assert adapter.get_idade_origem("PETR4") is None
        adapter.desconectar()

    def test_get_idade_origem_epoch_valida(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        agora = time.time()
        server.push("PETR4", "TIMENEG", f"{agora - 3.0:.3f}")
        time.sleep(0.1)
        idade = adapter.get_idade_origem("PETR4")
        assert idade is not None
        assert 2.0 <= idade <= 5.0
        adapter.desconectar()

    def test_get_idade_origem_futuro_invalido(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "TIMENEG", f"{time.time() + 7200.0:.3f}")
        time.sleep(0.1)
        assert adapter.get_idade_origem("PETR4") is None
        adapter.desconectar()
