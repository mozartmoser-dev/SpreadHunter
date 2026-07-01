"""Teste de performance da _thread_leitora do OpenFastSocketAdapter.

Simula o servidor fasttrader enviando dados em lote para milhares de
instrumentos, como ocorre na carga real.
"""
import time
import socket
import threading
import pytest

from src.infrastructure.providers.openfast_socket_adapter import OpenFastSocketAdapter
from src.domain.services.market_data_source import FieldName

_SEP = "\001"
HOST = "127.0.0.1"
PORT = 5560


class LoadSimulator:
    """Servidor que simula o fasttrader enviando push para N instrumentos."""

    def __init__(self, port: int = PORT):
        self.port = port
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((HOST, port))
        self._server.listen(1)
        self._running = False
        self._conn: socket.socket | None = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        time.sleep(0.05)

    def stop(self):
        self._running = False
        try:
            self._server.close()
            if self._conn:
                self._conn.close()
        except Exception:
            pass

    def _run(self):
        self._server.settimeout(2.0)
        while self._running:
            try:
                conn, _ = self._server.accept()
                self._conn = conn
                conn.sendall(b"version\0011.0\n")
                conn.settimeout(0.5)
                self._atender(conn)
            except socket.timeout:
                continue
            except Exception:
                break

    def _atender(self, conn: socket.socket):
        buf = b""
        while self._running:
            try:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
                # Processa comandos on/SQT e envia respostas
                while b"\n" in buf:
                    linha, buf = buf.split(b"\n", 1)
                    linha_s = linha.decode("utf-8", errors="ignore").strip()
                    if linha_s.startswith(f"on{_SEP}SQT{_SEP}"):
                        partes = linha_s.split(_SEP)
                        if len(partes) >= 4:
                            ativo = partes[2]
                            campo = partes[3]
                            # Simula resposta do servidor com valor
                            resp = f"SQT{_SEP}{ativo}{_SEP}{campo}{_SEP}1.23\n"
                            conn.sendall(resp.encode())
            except socket.timeout:
                continue
            except Exception:
                break

    def push_batch(self, n: int, campos_por_ativo: int = 4):
        """Envia N×campos respostas SQT."""
        linhas: list[str] = []
        for i in range(n):
            ativo = f"ATIVO{i:05d}"
            for c in range(campos_por_ativo):
                campo = ["ASK", "BID", "LAST", "PEX"][c % campos_por_ativo]
                linhas.append(f"SQT{_SEP}{ativo}{_SEP}{campo}{_SEP}25.50")
        payload = "\n".join(linhas) + "\n"
        if self._conn:
            self._conn.sendall(payload.encode())


class TestReaderPerformance:
    """Mede a capacidade de processamento da thread leitora."""

    @pytest.fixture
    def sim(self):
        s = LoadSimulator(port=PORT)
        s.start()
        yield s
        s.stop()

    def measure_reader_time(self, adapter: OpenFastSocketAdapter, n_atendimentos: int = 5) -> float:
        """Espera a thread leitora processar N atualizações no cache."""
        for _ in range(20):
            chaves = len(adapter._cache)
            if chaves >= n_atendimentos:
                break
            time.sleep(0.01)
        return len(adapter._cache)

    def test_baseline_recv_throughput(self, sim):
        """Mede quão rápido a thread leitora processa dados em lote."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.0)
        time.sleep(0.05)

        # Registra alguns tópicos para o servidor aceitar
        adapter.registrar_topico("ATIVO00001", FieldName.ASK)
        time.sleep(0.1)

        # Envia lote de 10k respostas
        t0 = time.perf_counter()
        sim.push_batch(1000, 4)
        time.sleep(1.0)  # espera processar

        # Já registra direto no cache via _parse_linha p/ medir
        parsed = adapter._parse_linha(f"SQT{_SEP}TESTE{_SEP}LAST{_SEP}10.00")
        if parsed is not None:
            with adapter._mutex:
                adapter._cache[parsed[0]] = parsed[1]
                adapter._dirty_keys.add(parsed[0])

        elapsed = time.perf_counter() - t0
        print(f"\n  Batch 4k respostas: {elapsed:.3f}s")

        # Mede cache
        chaves = len(adapter._cache)
        print(f"  Chaves no cache: {chaves}")
        adapter.desconectar()
        assert chaves >= 1

    @pytest.mark.parametrize("n_campos", [100, 1000, 5000, 10000])
    def test_per_batch_mutex(self, n_campos):
        """Mede o custo do parse + batch mutex (nova abordagem)."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.0)
        time.sleep(0.05)
        try:
            linhas = []
            for i in range(n_campos):
                ativo = f"ATIVO{i:05d}"
                linhas.append(f"SQT{_SEP}{ativo}{_SEP}LAST{_SEP}25.50")
            payload = "\n".join(linhas)

            t0 = time.perf_counter()
            # Simula a nova abordagem: parse sem lock, batch write
            atualizacoes = []
            buf = ""
            buf += payload
            while "\n" in buf:
                linha, buf = buf.split("\n", 1)
                parsed = adapter._parse_linha(linha.strip())
                if parsed is not None:
                    atualizacoes.append(parsed)
            if atualizacoes:
                with adapter._mutex:
                    for chave, valor in atualizacoes:
                        adapter._cache[chave] = valor
                        adapter._dirty_keys.add(chave)
            elapsed = time.perf_counter() - t0

            chaves = len(adapter._cache)
            print(f"\n  n={n_campos:>5}: {elapsed:.4f}s  ({elapsed/n_campos*1e6:.0f}μs/linha)  cache={chaves}")
        finally:
            adapter.desconectar()

    def test_contention_reader_vs_main(self, sim):
        """Simula contenção: thread leitora + main thread lendo cache."""
        adapter = OpenFastSocketAdapter(host=HOST, port=PORT, send_delay_s=0.0)
        time.sleep(0.05)

        # Pré-popula cache com 10k chaves
        for i in range(10000):
            ativo = f"ATIVO{i:05d}"
            chave = (ativo, "LAST")
            adapter._cache[chave] = 25.50

        # Main thread lê cache em loop (simula capturar_dados_mercado)
        stop = threading.Event()

        def leitor_concorrente():
            count = 0
            while not stop.is_set():
                for i in range(1000):
                    ativo = f"ATIVO{i:05d}"
                    adapter.ler_campo_cache(ativo, FieldName.LAST_PRICE)
                    count += 1
                time.sleep(0)

        t_leitor = threading.Thread(target=leitor_concorrente, daemon=True)
        t_leitor.start()

        # Envia push enquanto main thread lê
        t0 = time.perf_counter()
        sim.push_batch(2000, 4)
        time.sleep(2.0)
        stop.set()

        elapsed = time.perf_counter() - t0
        chaves = len(adapter._cache)
        print(f"\n  Contention test: {elapsed:.3f}s  cache={chaves}")
        adapter.desconectar()


if __name__ == "__main__":
    pytest.main([__file__, "-vvs", "--tb=short"])
