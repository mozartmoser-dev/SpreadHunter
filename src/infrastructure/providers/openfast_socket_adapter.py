import socket
import threading
import time
import logging
from src.domain.services.market_data_source import FieldName, OPENFAST_FIELD_STR

logger = logging.getLogger(__name__)

_SEP = "\001"
_STATUS_NORMALIZE = {
    "A": "Aberto", "ABERTO": "Aberto",
    "L": "Leilão", "LEILAO": "Leilão",
    "F": "Fechado", "FECHADO": "Fechado",
}


class OpenFastSocketAdapter:
    suporta_push: bool = True
    suporta_cab_skip: bool = False

    def __init__(self, host: str = "127.0.0.1", port: int = 557,
                 send_delay_s: float = 0.005):
        self._host = host
        self._port = port
        self._send_delay_s = send_delay_s
        self._socket: socket.socket | None = None
        self._conectado: bool = False
        self._cache: dict[tuple[str, str], object] = {}
        self._dirty_keys: set[tuple[str, str]] = set()
        self._ultimo_syn: float = 0.0
        self._mutex = threading.Lock()
        self._subscriptions: list[tuple[str, str]] = []
        self._reader_thread: threading.Thread | None = None
        self._conectar()

    @property
    def disponivel(self) -> bool:
        if not self._conectado:
            return False
        return time.time() - self._ultimo_syn < 20.0

    def _conectar(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(5.0)
            self._socket.connect((self._host, self._port))
            self._socket.sendall(b"OPENFAST\n")
            resp = self._socket.recv(1024).decode("utf-8", errors="ignore").strip()
            if not resp.startswith("version"):
                raise ConnectionError(f"Handshake inesperado: {resp!r}")
            self._socket.settimeout(1.0)
            self._conectado = True
            self._ultimo_syn = time.time()
            self._reader_thread = threading.Thread(
                target=self._thread_leitora, daemon=True
            )
            self._reader_thread.start()
            logger.info("Open Fast conectado em %s:%d", self._host, self._port)
        except Exception as e:
            self._conectado = False
            logger.warning("Open Fast: falha na conexão: %s", e)

    def reconectar(self) -> bool:
        self.desconectar()
        self._conectar()
        if self._conectado:
            self._re_registrar_pendentes()
        return self._conectado

    def _re_registrar_pendentes(self):
        for codigo, campo_str in self._subscriptions:
            self._enviar_raw(f"on{_SEP}SQT{_SEP}{codigo}{_SEP}{campo_str}")

    def registrar_topico(self, codigo: str, campo: FieldName) -> int:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if campo_str is None:
            return -1
        self._enviar_raw(f"on{_SEP}SQT{_SEP}{codigo}{_SEP}{campo_str}")
        with self._mutex:
            entry = (codigo.upper(), campo_str)
            if entry not in self._subscriptions:
                self._subscriptions.append(entry)
        return 0

    def registrar_status(self, codigo: str) -> int:
        return self.registrar_topico(codigo, FieldName.STATUS)

    def _enviar_raw(self, comando: str):
        try:
            with self._mutex:
                if self._socket:
                    self._socket.sendall((comando + "\n").encode("utf-8"))
        except Exception as e:
            logger.warning("Open Fast: erro ao enviar: %s", e)
            self._conectado = False
        time.sleep(self._send_delay_s)

    def ler_campo_cache(self, codigo: str, campo: FieldName) -> float | None:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return None
        with self._mutex:
            raw = self._cache.get((codigo.upper(), campo_str))
        if raw is None:
            return None
        try:
            v = float(str(raw).replace(",", "."))
            return v if v > 0 else 0.0
        except (ValueError, TypeError):
            return None

    def ler_status_cache(self, codigo: str) -> str:
        with self._mutex:
            raw = self._cache.get((codigo.upper(), "ST"), "")
        return _STATUS_NORMALIZE.get(str(raw).upper(), str(raw))

    def forcar_leitura(self, codigo: str, campo: FieldName) -> float | None:
        self.registrar_topico(codigo, campo)
        for _ in range(5):
            v = self.ler_campo_cache(codigo, campo)
            if v is not None:
                return v
            time.sleep(0.01)
        return self.ler_campo_cache(codigo, campo)

    def refresh(self, timeout_ms: int = 0) -> dict[str, object]:
        with self._mutex:
            mudancas = {
                f"{cod}|{campo}": self._cache.get((cod, campo))
                for cod, campo in self._dirty_keys
            }
            self._dirty_keys.clear()
        return mudancas

    def _thread_leitora(self):
        buffer = ""
        meu_socket = self._socket
        while self._conectado:
            try:
                dados = meu_socket.recv(4096).decode("utf-8", errors="ignore")
                if not dados:
                    self._conectado = False
                    break
                buffer += dados
                while "\n" in buffer:
                    linha, buffer = buffer.split("\n", 1)
                    self._processar_linha(linha.strip())
            except socket.timeout:
                continue
            except Exception as e:
                logger.warning("Open Fast: leitura interrompida: %s", e)
                with self._mutex:
                    if self._socket is meu_socket:
                        self._conectado = False
                break

    def _processar_linha(self, linha: str):
        if not linha:
            return
        try:
            sep = _SEP if _SEP in linha else "#"
            partes = linha.split(sep)
            if partes[0] == "SYN":
                self._ultimo_syn = time.time()
                return
            if len(partes) < 4 or partes[0] != "SQT":
                logger.debug("Open Fast: linha ignorada: %s", linha[:80])
                return
            _, cod, campo, valor_str = partes[0], partes[1], partes[2], partes[3]
            valor_str = valor_str.replace(",", ".")
            try:
                valor = float(valor_str)
            except ValueError:
                valor = valor_str
            chave = (cod.upper(), campo)
            with self._mutex:
                self._cache[chave] = valor
                self._dirty_keys.add(chave)
        except Exception as e:
            logger.debug("Open Fast: erro parse: %s — %s", e, linha[:100])

    def invalidar_cache(self, codigo: str, campo: FieldName):
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return
        with self._mutex:
            self._cache.pop((codigo.upper(), campo_str), None)

    def desconectar(self):
        self._conectado = False
        try:
            if self._socket:
                self._socket.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            if self._socket:
                self._socket.close()
        except Exception:
            pass
        self._socket = None
