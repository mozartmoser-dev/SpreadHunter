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
                 send_delay_s: float = 0.0):
        self._host = host
        self._port = port
        self._send_delay_s = send_delay_s
        self._socket: socket.socket | None = None
        self._conectado: bool = False
        self._cache: dict[tuple[str, str], object] = {}
        self._cache_ts: dict[tuple[str, str], float] = {}
        self._dirty_keys: set[tuple[str, str]] = set()
        self._update_counter: int = 0
        self._ultimo_syn: float = 0.0
        self._mutex = threading.Lock()
        self._subscriptions: list[tuple[str, str]] = []
        self._subs_set: set[tuple[str, str]] = set()
        self._reader_thread: threading.Thread | None = None
        self._prof_recv_calls = 0
        self._prof_recv_bytes = 0
        self._prof_recv_time = 0.0
        self._prof_parse_time = 0.0
        self._prof_mutex_time = 0.0
        self._prof_linhas = 0
        self._prof_concat_time = 0.0
        self._prof_split_time = 0.0
        self._prof_last_log = 0.0
        self._PROF_LOG_INTERVAL = 30.0
        self._conectar()

    def __del__(self):
        try:
            self.desconectar()
        except Exception:
            pass

    def set_send_delay(self, delay_ms: int):
        self._send_delay_s = max(0.0, delay_ms / 1000.0)

    @property
    def disponivel(self) -> bool:
        if not self._conectado:
            return False
        return time.time() - self._ultimo_syn < 20.0

    @property
    def update_counter(self) -> int:
        with self._mutex:
            return self._update_counter

    def _conectar(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)
            self._socket.settimeout(5.0)
            self._socket.connect((self._host, self._port))
            self._socket.sendall(b"OPENFAST\n")
            buffer = ""
            linha_version = None
            expire = time.time() + 5.0
            while time.time() < expire:
                try:
                    chunk = self._socket.recv(4096).decode("utf-8", errors="ignore")
                    if not chunk:
                        break
                    buffer += chunk
                    if "\n" in buffer:
                        linhas = buffer.split("\n")
                        linha_version = next((l for l in linhas if l.strip().startswith("version")), None)
                        if linha_version:
                            break
                except socket.timeout:
                    continue
            if not linha_version:
                erro_msg = buffer.strip()[:200]
                logger.warning("Open Fast: handshake sem version line: %s", erro_msg)
                if "mais de uma conex" in erro_msg.lower():
                    logger.info("Open Fast: servidor ocupado (outro cliente conectado).")
                    self._socket.close()
                    self._socket = None
                    self._conectado = False
                    return
            if self._socket is not None:
                self._socket.settimeout(1.0)
                self._conectado = True
                self._ultimo_syn = time.time()
                self._reader_thread = threading.Thread(
                    target=self._thread_leitora, daemon=True
                )
                self._reader_thread.start()
                logger.info("Open Fast conectado em %s:%d — handshake: %s",
                            self._host, self._port, buffer[:120].replace("\r\n", "; "))
        except Exception as e:
            self._conectado = False
            logger.warning("Open Fast: falha na conexão: %s", e)

    def reconectar(self, max_attempts: int = 5, delay_s: float = 3.0) -> bool:
        self.desconectar()
        for tentativa in range(1, max_attempts + 1):
            self._conectar()
            if self._conectado:
                self._re_registrar_pendentes()
                return True
            if tentativa < max_attempts:
                time.sleep(delay_s * tentativa)
        return False

    def _re_registrar_pendentes(self):
        for codigo, campo_str in self._subscriptions:
            self._enviar_raw(f"on{_SEP}SQT{_SEP}{codigo.upper()}{_SEP}{campo_str}")

    def registrar_topico(self, codigo: str, campo: FieldName) -> int:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if campo_str is None:
            return -1
        self._enviar_raw(f"on{_SEP}SQT{_SEP}{codigo.upper()}{_SEP}{campo_str}")
        with self._mutex:
            entry = (codigo.upper(), campo_str)
            if entry not in self._subs_set:
                self._subs_set.add(entry)
                self._subscriptions.append(entry)
        return 0

    def registrar_lista(self, registros: list[tuple[str, FieldName]]) -> int:
        if not registros:
            return 0
        linhas: list[str] = []
        entradas: list[tuple[str, str]] = []
        for codigo, campo in registros:
            campo_str = OPENFAST_FIELD_STR.get(campo)
            if not campo_str:
                continue
            upper = codigo.upper()
            linhas.append(f"on{_SEP}SQT{_SEP}{upper}{_SEP}{campo_str}")
            entradas.append((upper, campo_str))
        if not linhas:
            return 0
        self._enviar_raw("\n".join(linhas))
        with self._mutex:
            for entry in entradas:
                if entry not in self._subs_set:
                    self._subs_set.add(entry)
                    self._subscriptions.append(entry)
        return len(entradas)

    def registrar_status(self, codigo: str) -> int:
        return self.registrar_topico(codigo, FieldName.STATUS)

    def _enviar_raw(self, comando: str):
        try:
            sock = self._socket
            if sock is None:
                return
            sock.sendall((comando + "\n").encode("utf-8"))
        except Exception as e:
            logger.warning("Open Fast: erro ao enviar: %s", e)
            self._conectado = False
        time.sleep(max(self._send_delay_s, 0.001))

    def ler_campo_cache(self, codigo: str, campo: FieldName) -> float | None:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return None
        chave = (codigo.upper(), campo_str)
        with self._mutex:
            raw = self._cache.get(chave)
            ts = self._cache_ts.get(chave)
        if raw is None:
            return None
        if ts is not None and time.time() - ts > 120:
            return None
        try:
            v = float(str(raw).replace(",", "."))
            return 0.0 if v == 0 else v
        except (ValueError, TypeError):
            return None

    def ler_campos(self, codigo: str, *campos: FieldName) -> dict[FieldName, float | None]:
        resultado: dict[FieldName, float | None] = {}
        upper = codigo.upper()
        agora = time.time()
        with self._mutex:
            for campo in campos:
                campo_str = OPENFAST_FIELD_STR.get(campo)
                if not campo_str:
                    resultado[campo] = None
                    continue
                chave = (upper, campo_str)
                raw = self._cache.get(chave)
                if raw is None:
                    resultado[campo] = None
                    continue
                ts = self._cache_ts.get(chave)
                if ts is not None and agora - ts > 120:
                    resultado[campo] = None
                    continue
                try:
                    v = float(str(raw).replace(",", "."))
                    resultado[campo] = 0.0 if v == 0 else v
                except (ValueError, TypeError):
                    resultado[campo] = None
        return resultado

    def ler_status_cache(self, codigo: str) -> str:
        with self._mutex:
            raw = self._cache.get((codigo.upper(), "ST"), "")
        return _STATUS_NORMALIZE.get(str(raw).upper(), str(raw))

    def forcar_leitura(self, codigo: str, campo: FieldName) -> float | None:
        old = self.ler_campo_cache(codigo, campo)
        self.invalidar_cache(codigo, campo)
        self.registrar_topico(codigo, campo)
        for _ in range(50):
            v = self.ler_campo_cache(codigo, campo)
            if v is not None and v > 0:
                return v
            time.sleep(0.01)
        return old

    def refresh(self, timeout_ms: int = 0) -> dict[str, object]:
        with self._mutex:
            mudancas = {
                f"{cod}|{campo}": self._cache.get((cod, campo))
                for cod, campo in self._dirty_keys
            }
            self._dirty_keys.clear()
        return mudancas

    def _log_profile(self):
        agora = time.time()
        if agora - self._prof_last_log < self._PROF_LOG_INTERVAL:
            return
        self._prof_last_log = agora
        t_recv = self._prof_recv_time
        t_parse = self._prof_parse_time
        t_mutex = self._prof_mutex_time
        t_concat = self._prof_concat_time
        t_split = self._prof_split_time
        n_linhas = self._prof_linhas
        n_recv = self._prof_recv_calls
        n_bytes = self._prof_recv_bytes
        total = t_recv + t_parse + t_mutex + t_concat + t_split
        logger.info(
            "OF Prof: recv=%d/%dKB(%.1fs) parse=%.1fs mutex=%.1fs concat=%.1fs split=%.1fs "
            "linhas=%d total=%.1fs",
            n_recv, n_bytes // 1024, t_recv, t_parse, t_mutex, t_concat, t_split,
            n_linhas, total,
        )
        self._prof_recv_calls = 0
        self._prof_recv_bytes = 0
        self._prof_recv_time = 0.0
        self._prof_parse_time = 0.0
        self._prof_mutex_time = 0.0
        self._prof_linhas = 0
        self._prof_concat_time = 0.0
        self._prof_split_time = 0.0

    def _thread_leitora(self):
        buffer = ""
        atualizacoes: list[tuple[tuple[str, str], object]] = []
        meu_socket = self._socket
        self._prof_last_log = time.time()
        while self._conectado:
            try:
                t0 = time.perf_counter()
                dados = meu_socket.recv(65536)
                self._prof_recv_calls += 1
                self._prof_recv_time += time.perf_counter() - t0
                if not dados:
                    self._conectado = False
                    break
                texto = dados.decode("utf-8", errors="ignore")
                self._prof_recv_bytes += len(dados)

                t0 = time.perf_counter()
                buffer += texto
                self._prof_concat_time += time.perf_counter() - t0

                while "\n" in buffer:
                    t0 = time.perf_counter()
                    linha, buffer = buffer.split("\n", 1)
                    self._prof_split_time += time.perf_counter() - t0
                    linha = linha.strip()
                    if not linha:
                        continue
                    self._prof_linhas += 1
                    if linha.startswith("SYN"):
                        self._ultimo_syn = time.time()
                        continue
                    parsed = self._parse_linha(linha)
                    if parsed is not None:
                        atualizacoes.append(parsed)

                if atualizacoes:
                    t0 = time.perf_counter()
                    agora = time.time()
                    with self._mutex:
                        for chave, valor in atualizacoes:
                            self._cache[chave] = valor
                            self._cache_ts[chave] = agora
                            self._dirty_keys.add(chave)
                        self._update_counter += 1
                    self._prof_mutex_time += time.perf_counter() - t0
                    atualizacoes.clear()
            except socket.timeout:
                self._log_profile()
                continue
            except Exception as e:
                logger.warning("Open Fast: leitura interrompida: %s", e)
                with self._mutex:
                    if self._socket is meu_socket:
                        self._conectado = False
                break

    def _parse_linha(self, linha: str) -> tuple[tuple[str, str], object] | None:
        try:
            sep = _SEP if _SEP in linha else "#"
            partes = linha.split(sep)
            if len(partes) < 4 or partes[0] != "SQT":
                logger.debug("Open Fast: linha ignorada: %s", linha[:80])
                return None
            _, cod, campo, valor_str = partes[0], partes[1], partes[2], partes[3]
            t0 = time.perf_counter()
            valor_str = valor_str.replace(",", ".")
            try:
                valor = float(valor_str)
            except ValueError:
                valor = valor_str
            chave = (cod.upper(), campo)
            self._prof_parse_time += time.perf_counter() - t0
            return (chave, valor)
        except Exception as e:
            logger.debug("Open Fast: erro parse: %s — %s", e, linha[:100])
            return None

    def invalidar_cache(self, codigo: str, campo: FieldName):
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return
        with self._mutex:
            self._cache.pop((codigo.upper(), campo_str), None)

    def get_idade_campo(self, codigo: str, campo: FieldName) -> float | None:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return None
        with self._mutex:
            ts = self._cache_ts.get((codigo.upper(), campo_str))
        if ts is None:
            return None
        return time.time() - ts

    def get_ts_campo(self, codigo: str, campo: FieldName) -> float | None:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return None
        with self._mutex:
            return self._cache_ts.get((codigo.upper(), campo_str))

    def desconectar(self):
        self._conectado = False
        time.sleep(0.05)
        with self._mutex:
            self._cache.clear()
            self._cache_ts.clear()
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
