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

    def test_forcar_leitura(self, server):
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.001)
        server.push("PETR4", "BID", "1.23")
        time.sleep(0.1)
        v = adapter.forcar_leitura("PETR4", FieldName.BID)
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
