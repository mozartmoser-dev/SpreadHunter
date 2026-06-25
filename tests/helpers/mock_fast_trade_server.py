import socket
import threading
import time


class MockFastTradeServer:
    """Servidor TCP fake que emula Open Fast. Porta 5557 para não conflitar."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5557):
        self.host = host
        self.port = port
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((host, port))
        self._server.listen(5)
        self._running = False
        self._conn: socket.socket | None = None
        self._conn_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._subscriptions: dict[str, set[str]] = {}

    def start(self):
        self._running = True
        self._thread.start()
        time.sleep(0.05)

    def stop(self):
        self._running = False
        try:
            self._server.close()
            with self._conn_lock:
                if self._conn:
                    self._conn.close()
        except Exception:
            pass

    def push(self, ativo: str, campo: str, valor):
        """Simula chegada de SQT."""
        with self._conn_lock:
            conn = self._conn
        if conn:
            try:
                msg = f"SQT\001{ativo}\001{campo}\001{valor}\n"
                conn.sendall(msg.encode())
            except Exception:
                pass

    def send_syn(self):
        with self._conn_lock:
            conn = self._conn
        if conn:
            try:
                conn.sendall(b"SYN\n")
            except Exception:
                pass

    def _run(self):
        self._server.settimeout(1.0)
        while self._running:
            try:
                conn, _ = self._server.accept()
                with self._conn_lock:
                    self._conn = conn
                t = threading.Thread(target=self._atender, args=(conn,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break

    def _atender(self, conn: socket.socket):
        try:
            conn.sendall(b"version\0011.0\n")
            conn.settimeout(1.0)
            buffer = ""
            while self._running:
                try:
                    dados = conn.recv(4096).decode("utf-8", errors="ignore")
                    if not dados:
                        break
                    buffer += dados
                    while "\n" in buffer:
                        cmd, buffer = buffer.split("\n", 1)
                        cmd = cmd.strip()
                        if cmd.startswith("on\001SQT\001") or cmd.startswith("on#SQT#"):
                            sep = "\001" if "\001" in cmd else "#"
                            partes = cmd.split(sep)
                            if len(partes) >= 4:
                                ativo = partes[2]
                                campo = partes[3]
                                self._subscriptions.setdefault(ativo, set()).add(campo)
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            try:
                conn.close()
            except Exception:
                pass
