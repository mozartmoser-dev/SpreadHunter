import socket
import threading
import time
import logging
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from src.domain.services.market_data_source import FieldName, OPENFAST_FIELD_STR
from src.infrastructure.providers import stale_trace

logger = logging.getLogger(__name__)

_SEP = "\001"
_TZ_BR = ZoneInfo("America/Sao_Paulo")
_EPOCH_MIN = 1_000_000_000
_SECS_PER_DAY = 86400.0
_STATUS_NORMALIZE = {
    "A": "Aberto", "ABERTO": "Aberto",
    "L": "Leilão", "LEILAO": "Leilão",
    "F": "Fechado", "FECHADO": "Fechado",
}


def _midnight_brt_epoch() -> float:
    """Meia-noite do dia corrente em America/Sao_Paulo como epoch Unix."""
    agora_brt = datetime.now(_TZ_BR)
    midnight = agora_brt.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.timestamp()


def _normalizar_status(status: str) -> str:
    """Remove acento combinante para comparacao robusta (ex.: 'Leil?o' do servidor)."""
    chave = unicodedata.normalize("NFD", status.upper())
    return "".join(c for c in chave if unicodedata.category(c) != "Mn")


def _normalizar_ts_origem(raw) -> float | None:
    """Normaliza TIME/TIMENEG do OpenFast para epoch Unix absoluto.

    O protocolo OpenFast pode entregar o horário como:
    - fração de dia decimal (ex.: "0,712719907407407"), estilo Excel/FAST;
    - texto "hh:mm:ss" ou "hh:mm:ss.ffffff";
    - epoch Unix já absoluto (>= 1_000_000_000);
    - "0" ou vazio quando não há timestamp disponível.

    A data de referência para fração/hora é o dia corrente em America/Sao_Paulo
    (timezone de mercado já usada em todo o restante do sistema).

    Retorna epoch Unix (float, segundos) ou None quando o valor é ausente,
    zero, ou não interpretável.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if ":" in s:
        s_norm = s.replace(",", ".")
        parts = s_norm.split(":")
        if len(parts) != 3:
            return None
        try:
            h = int(parts[0])
            m = int(parts[1])
            segundos = float(parts[2])
        except (ValueError, TypeError):
            return None
        if not (0 <= h <= 23 and 0 <= m <= 59 and 0.0 <= segundos < 60.0):
            return None
        return _midnight_brt_epoch() + (h * 3600 + m * 60 + segundos)
    try:
        v = float(s.replace(",", "."))
    except (ValueError, TypeError):
        return None
    if v == 0:
        return None
    if v >= _EPOCH_MIN:
        return v
    if 0.0 < v < 1.0:
        return _midnight_brt_epoch() + v * _SECS_PER_DAY
    return None


def _normalizar_ts_timeneg(raw) -> float | None:
    """Normaliza TIMENEG (hora do último negócio) para epoch Unix absoluto.

    O protocolo não envia a data do último negócio, apenas a hora do dia, e
    não garante relação temporal com TIME: cada campo é uma mensagem SQT
    independente, então TIMENEG pode legitimamente ser maior que TIME dentro do
    mesmo pregão. O horário é sempre ancorado no dia corrente em
    America/Sao_Paulo, sem retroceder para um pregão anterior:

    - "00:00:00"/"00:00"/zero/vazio        -> None (sentinela "sem negócio");
    - "hh:mm:ss[.ffffff]" ou fração de dia -> dia corrente (BRT);
    - epoch Unix absoluto (>= 1e9)         -> preservado, data intacta.

    TIME, T0 e os tempos de entrega (T1..T4) não passam por esta função.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s == "0":
        return None
    if ":" in s:
        partes = s.replace(",", ".").split(":")
        if len(partes) == 3:
            try:
                h, m, seg = int(partes[0]), int(partes[1]), float(partes[2])
                if h == 0 and m == 0 and seg == 0:
                    return None  # sentinela "sem negócio" (00:00:00)
            except (ValueError, TypeError):
                pass
    else:
        try:
            v = float(s.replace(",", "."))
        except (ValueError, TypeError):
            v = None
        if v is not None and v >= _EPOCH_MIN:
            return v  # epoch Unix absoluto: preservado, data intacta
    return _normalizar_ts_origem(s)


class OpenFastSocketAdapter:
    suporta_push: bool = True
    suporta_cab_skip: bool = False

    def __init__(self, host: str = "127.0.0.1", port: int = 557,
                 send_delay_s: float = 0.0, stale_campo_s: float = 15.0):
        self._host = host
        self._port = port
        self._send_delay_s = send_delay_s
        self._stale_campo_s = float(stale_campo_s)
        self._socket: socket.socket | None = None
        self._conectado: bool = False
        self._feed_state: str = "desconectado"
        self._subscription_generation: int = 0
        self._cache: dict[tuple[str, str], object] = {}
        self._cache_ts: dict[tuple[str, str], float] = {}
        self._cache_ver: dict[tuple[str, str], int] = {}
        self._dirty_keys: set[tuple[str, str]] = set()
        self._update_counter: int = 0
        self._ultimo_syn: float = 0.0
        self._last_syn_ts: float = 0.0
        self._mutex = threading.Lock()
        self._subscriptions: list[tuple[str, str]] = []
        self._subs_set: set[tuple[str, str]] = set()
        self._reader_thread: threading.Thread | None = None
        self._watchdog_enabled: bool = True
        self._last_watchdog_check: float = 0.0
        self._cont_no_new_update: int = 0
        self._recv_seq = 0
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

    @property
    def feed_state(self) -> str:
        return self._feed_state

    @property
    def subscription_generation(self) -> int:
        return self._subscription_generation

    @property
    def cont_no_new_update(self) -> int:
        return self._cont_no_new_update

    @property
    def stale_campo_s(self) -> float:
        return self._stale_campo_s

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
                    stale_trace.log_evento("conectar", f"falha handshake: {erro_msg.strip()[:80]}")
                    return
            if self._socket is not None:
                self._socket.settimeout(1.0)
                self._conectado = True
                self._ultimo_syn = time.time()
                self._subscription_generation += 1
                self._feed_state = "conectado"
                stale_trace.log_evento("conectar", f"ok geracao={self._subscription_generation}", flush=True)
                self._reader_thread = threading.Thread(
                    target=self._thread_leitora, daemon=True
                )
                self._reader_thread.start()
                logger.info("Open Fast conectado em %s:%d — handshake: %s (geração %d)",
                            self._host, self._port, buffer[:120].replace("\r\n", "; "),
                            self._subscription_generation)
        except Exception as e:
            self._conectado = False
            logger.warning("Open Fast: falha na conexão: %s", e)

    def reconectar(self, max_attempts: int = 5, delay_s: float = 3.0) -> bool:
        self.desconectar()
        for tentativa in range(1, max_attempts + 1):
            self._conectar()
            if self._conectado:
                self._re_registrar_pendentes()
                stale_trace.log_evento("reconectar", f"ok geracao={self._subscription_generation}", flush=True)
                return True
            if tentativa < max_attempts:
                time.sleep(delay_s * tentativa)
        stale_trace.log_evento("reconectar", "falha", flush=True)
        return False

    def _re_registrar_pendentes(self):
        for codigo, campo_str in self._subscriptions:
            if stale_trace.matches(codigo, campo_str):
                stale_trace.log_evento("rassinar", f"{codigo.upper()}|{campo_str}")
            self._enviar_raw(f"on{_SEP}SQT{_SEP}{codigo.upper()}{_SEP}{campo_str}")

    def registrar_topico(self, codigo: str, campo: FieldName) -> int:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if campo_str is None:
            return -1
        self._enviar_raw(f"on{_SEP}SQT{_SEP}{codigo.upper()}{_SEP}{campo_str}")
        if stale_trace.matches(codigo, campo_str):
            stale_trace.log_evento("assinar", f"{codigo.upper()}|{campo_str}")
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

    def ler_campo_cache(self, codigo: str, campo: FieldName,
                        allow_stale: bool = False) -> float | None:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return None
        chave = (codigo.upper(), campo_str)
        with self._mutex:
            raw = self._cache.get(chave)
            ts = self._cache_ts.get(chave)
        if raw is None:
            return None
        if not allow_stale and ts is not None and (time.time() - ts) > self._stale_campo_s:
            return None
        try:
            v = float(str(raw).replace(",", "."))
            return v if v > 0 else (0.0 if v == 0 else None)
        except (ValueError, TypeError):
            return None

    def ler_campos(self, codigo: str, *campos: FieldName,
                   allow_stale: bool = False) -> dict[FieldName, float | None]:
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
                if not allow_stale and ts is not None and (agora - ts) > self._stale_campo_s:
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
        s = str(raw)
        conhecido = _STATUS_NORMALIZE.get(s.upper(), "")
        if conhecido:
            return conhecido
        if _normalizar_status(s).startswith("LEIL"):
            return "Leilão"
        return s

    def forcar_leitura(self, codigo: str, campo: FieldName,
                       allow_stale: bool = False, timeout_ms: int = 500) -> float | None:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return None
        chave = (codigo.upper(), campo_str)
        with self._mutex:
            ver_antes = self._cache_ver.get(chave, 0)
        self.registrar_topico(codigo, campo)
        limite = time.time() + (timeout_ms / 1000.0)
        while time.time() < limite:
            with self._mutex:
                ver_atual = self._cache_ver.get(chave, 0)
            if ver_atual > ver_antes:
                return self.ler_campo_cache(codigo, campo, allow_stale=allow_stale)
            time.sleep(0.01)
        if allow_stale:
            return self.ler_campo_cache(codigo, campo, allow_stale=True)
        self._cont_no_new_update += 1
        stale_trace.log_evento("no_new_update", f"{codigo.upper()}|{campo_str}")
        logger.warning("OpenFast NO_NEW_UPDATE forcar_leitura %s|%s (sem push novo em %dms)",
                       codigo, campo_str, timeout_ms)
        return None

    def refresh(self, timeout_ms: int = 0) -> dict[str, object]:
        with self._mutex:
            mudancas = {
                f"{cod}|{campo}": self._cache.get((cod, campo))
                for cod, campo in self._dirty_keys
            }
            for cod, campo in list(self._dirty_keys):
                if stale_trace.matches(cod, campo):
                    stale_trace.log_t4(cod, campo, self._cache.get((cod, campo)))
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
                    self._feed_state = "desconectado"
                    stale_trace.log_evento("desconectar", "recv vazio")
                    break
                texto = dados.decode("utf-8", errors="ignore")
                self._prof_recv_bytes += len(dados)
                self._recv_seq += 1
                ts_recv = time.time()
                stale_trace.log_recv(self._recv_seq, ts_recv, len(dados))

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
                        self._last_syn_ts = self._ultimo_syn
                        stale_trace.log_evento("syn")
                        continue
                    parsed = self._parse_linha(linha)
                    if parsed is not None:
                        (cod_t, campo_t), valor_t = parsed
                        if stale_trace.matches(cod_t, campo_t):
                            stale_trace.log_t1(self._recv_seq, ts_recv, cod_t, campo_t, valor_t)
                            stale_trace.log_t2(cod_t, campo_t, valor_t)
                        atualizacoes.append(parsed)

                if atualizacoes:
                    t0 = time.perf_counter()
                    agora = time.time()
                    with self._mutex:
                        if self._socket is not meu_socket or not self._conectado:
                            atualizacoes.clear()
                            continue
                        for chave, valor in atualizacoes:
                            self._cache[chave] = valor
                            self._cache_ts[chave] = agora
                            nova_ver = self._cache_ver.get(chave, 0) + 1
                            self._cache_ver[chave] = nova_ver
                            if stale_trace.matches(chave[0], chave[1]):
                                stale_trace.log_t3(chave[0], chave[1], valor, nova_ver)
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
                        self._feed_state = "desconectado"
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

    def is_stale_campo(self, codigo: str, campo: FieldName) -> bool:
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return True
        chave = (codigo.upper(), campo_str)
        with self._mutex:
            if chave not in self._cache:
                return False
            ts = self._cache_ts.get(chave)
        if ts is None:
            return False
        return (time.time() - ts) > self._stale_campo_s

    def get_ts_origem(self, codigo: str) -> float | None:
        """Timestamp de origem (TIME/TIMENEG do protocolo) quando assinado.

        Diagnóstico apenas: nunca atualiza _cache_ts (frescor de entrega).
        Prefere TIME (horário da mensagem de cotação); usa TIMENEG (horário do
        último negócio) como fallback.

        Normaliza o valor cru do OpenFast (fração de dia, "hh:mm:ss" ou epoch
        absoluto) para epoch Unix absoluto (mesma escala de time.time()).
        Retorna None quando o campo não foi assinado/recebido ou quando o
        valor é zero/vazio/inválido.
        """
        for campo in (FieldName.TIME, FieldName.TIMENEG):
            v = self._ts_normalizado(codigo, campo)
            if v is not None:
                return v
        return None

    def _ts_normalizado(self, codigo: str, campo: FieldName) -> float | None:
        """Normaliza um campo de horário cru do protocolo para epoch Unix.

        TIME e TIMENEG são ancorados no dia corrente em America/Sao_Paulo.
        TIMENEG passa por _normalizar_ts_timeneg apenas para tratar a sentinela
        "00:00:00" (sem negócio) — sem retroceder para um pregão anterior.

        Retorna None quando o campo não foi assinado/recebido ou quando o
        valor é zero/vazio/inválido.
        """
        campo_str = OPENFAST_FIELD_STR.get(campo)
        if not campo_str:
            return None
        with self._mutex:
            raw = self._cache.get((codigo.upper(), campo_str))
        if raw is None:
            return None
        if campo == FieldName.TIMENEG:
            return _normalizar_ts_timeneg(raw)
        return _normalizar_ts_origem(raw)

    def get_ts_time(self, codigo: str) -> float | None:
        """Horário da mensagem de cotação (TIME) normalizado para epoch Unix.

        Diagnóstico apenas: nunca atualiza _cache_ts (frescor de entrega).
        None se o campo TIME não foi assinado/recebido ou é inválido.
        """
        return self._ts_normalizado(codigo, FieldName.TIME)

    def get_ts_timeng(self, codigo: str) -> float | None:
        """Horário do último negócio (TIMENEG) normalizado para epoch Unix.

        Diagnóstico apenas: nunca atualiza _cache_ts (frescor de entrega).
        None se o campo TIMENEG não foi assinado/recebido ou é inválido.
        """
        return self._ts_normalizado(codigo, FieldName.TIMENEG)

    def get_idade_origem(self, codigo: str) -> float | None:
        """Idade real da cotação (agora - TIME/TIMENEG) quando o protocolo fornecer.

        None se o campo de origem não foi assinado/recebido, ou se o valor
        não for interpretável como timestamp absoluto (mesma escala de time.time()).
        Não substitui _cache_ts/is_stale_campo — é só diagnóstico.
        """
        origem = self.get_ts_origem(codigo)
        if origem is None:
            return None
        agora = time.time()
        if origem < 1_000_000_000 or origem > agora + 3600:
            return None
        return agora - origem

    def verificar_conexao(self) -> str:
        """Watchdog: thread leitora morta com _conectado ainda True -> DISCONNECTED.

        Invalida o cache: dados da sessão morta não devem ressuscitar no cálculo.
        """
        thread = self._reader_thread
        if not (self._conectado and self._watchdog_enabled
                and (thread is None or not thread.is_alive())):
            return self._feed_state
        logger.warning("OpenFast watchdog: thread leitora morta — marcando DESCONEXÃO.")
        stale_trace.log_evento("watchdog", "thread_leitora_morta", flush=True)
        with self._mutex:
            self._conectado = False
            self._feed_state = "desconectado"
            self._cache.clear()
            self._cache_ts.clear()
            self._cache_ver.clear()
            self._dirty_keys.clear()
        return self._feed_state

    def desconectar(self):
        self._conectado = False
        stale_trace.log_evento("desconectar", "chamada explicita")
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
        if self._reader_thread is not None and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=0.5)
        self._socket = None
        with self._mutex:
            self._cache.clear()
            self._cache_ts.clear()
            self._cache_ver.clear()
            self._dirty_keys.clear()
        self._feed_state = "desconectado"
