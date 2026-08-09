"""Instrumentação temporária de diagnóstico STALE OpenFast (pré-Fase 2).

Ativação: variável de ambiente SH_TRACE_CHAVE (sem espaço) com uma ou mais
chaves no formato "COD|CAMPO" separadas por ponto-e-vírgula.
Ex.: SH_TRACE_CHAVE=PETR4|ASK  ou  SH_TRACE_CHAVE=PETR44255|BID;PETR4|ASK

Modo tudo: SH_TRACE_CHAVE=*  (ou *|*) traça todos os códigos/campos — útil
porque filtrar uma chave pode mascarar o atraso no processamento do batch.

Auto-parada: SH_TRACE_LIMIT_S=<segundos> desliga o trace sozinho ao expirar
(para rodadas curtas tipo "5 minutos e parar" sem encher o disco).

Grava em <raiz>/logs/stale_trace.log (pipe-delimited, append, thread-safe).
NÃO altera lógica de negócio — apenas observa e registra. Remova após o
diagnóstico.

Linhas emitidas:
  RCV|seq|ts_iso|ts_unix|nbytes          — cada recv() da thread leitora
  T1|seq|ts_iso|ts_unix|cod|campo|valor  — linha SQT recebida (ts do recv que a trouxe)
  T2|ts_iso|ts_unix|cod|campo|valor      — parse da linha concluído
  T3|ts_iso|ts_unix|cod|campo|valor|ver  — cache atualizado (cache_ts=ver)
  T4|ts_iso|ts_unix|cod|campo|valor      — refresh() entregou a chave via dirty_keys
  T5|ts_iso|ts_unix|cod|campo|valor|idade_s|stale  — leitura no provider (montagem da entrada)
  T5|ts_iso|ts_unix|cod|campo|valor|idade_s|stale|UC — consumo direto num use case (BOX4P/PUT_RATIO/MPP)
  T6|ts_iso|ts_unix|ctx|elapsed_s|UC     — estágio de cálculo (ctx livre, UC opcional)
  EVT|ts_iso|ts_unix|tipo|detalhe        — conexão/SYN/assinatura/rassinar/STALE/etc.
"""

import os
import threading
import time
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "logs")
_LOG_PATH = os.path.join(_LOG_DIR, "stale_trace.log")

_START = time.monotonic()
_LIMIT_S = float(os.environ.get("SH_TRACE_LIMIT_S", "0") or 0)  # 0 = sem limite
_WILDCARD = False
_FIM = False

_lock = threading.Lock()
_buf: list[str] = []
_last_flush = time.monotonic()
_FLUSH_BYTES = 2048
_FLUSH_SECS = 1.0


def _parse_env() -> set[tuple[str, str]]:
    global _WILDCARD
    raw = os.environ.get("SH_TRACE_CHAVE", "")
    chaves: set[tuple[str, str]] = set()
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        if item == "*" or item == "*|*":
            _WILDCARD = True
            continue
        if "|" not in item:
            continue
        cod, campo = item.split("|", 1)
        chaves.add((cod.strip().upper(), campo.strip().upper()))
    return chaves


_TRAced: set[tuple[str, str]] = _parse_env()
_ENABLED = bool(_TRAced) or _WILDCARD


def enabled() -> bool:
    return _ENABLED and not _expirado()


def _expirado() -> bool:
    global _FIM
    if _LIMIT_S <= 0:
        return False
    if _FIM:
        return True
    if (time.monotonic() - _START) >= _LIMIT_S:
        _FIM = True
        _evt("trace_fim", f"limite_{_LIMIT_S:.0f}s", flush=True)
        return True
    return False


def traced_keys() -> set[tuple[str, str]]:
    return set(_TRAced)


def matches(cod: str, campo: str) -> bool:
    if not _ENABLED or _expirado():
        return False
    if _WILDCARD:
        return True
    return (cod.upper(), campo.upper()) in _TRAced


def _iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _flush():
    global _last_flush
    if not _buf:
        return
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(_buf) + "\n")
        _buf.clear()
        _last_flush = time.monotonic()
    except Exception:
        pass


def _write(linha: str, forcar_flush: bool = False):
    if not _ENABLED:
        return
    with _lock:
        _buf.append(linha)
        cur = len("\n".join(_buf))
        if (cur >= _FLUSH_BYTES
                or forcar_flush
                or (time.monotonic() - _last_flush) > _FLUSH_SECS):
            _flush()


def _evt(tipo: str, detalhe: str = "", flush: bool = False):
    _write(f"EVT|{_iso()}|{time.time():.6f}|{tipo}|{detalhe}", forcar_flush=flush)


def log_recv(seq: int, ts_recv: float, nbytes: int):
    _write(f"RCV|{seq}|{datetime.fromtimestamp(ts_recv).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}|{ts_recv:.6f}|{nbytes}")


def log_t1(seq: int, ts_recv: float, cod: str, campo: str, valor):
    if not matches(cod, campo):
        return
    _write(f"T1|{seq}|{datetime.fromtimestamp(ts_recv).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}|{ts_recv:.6f}|{cod}|{campo}|{valor}")


def log_t2(cod: str, campo: str, valor):
    if not matches(cod, campo):
        return
    _write(f"T2|{_iso()}|{time.time():.6f}|{cod}|{campo}|{valor}")


def log_t3(cod: str, campo: str, valor, ver: int):
    if not matches(cod, campo):
        return
    _write(f"T3|{_iso()}|{time.time():.6f}|{cod}|{campo}|{valor}|{ver}")


def log_t4(cod: str, campo: str, valor):
    if not matches(cod, campo):
        return
    _write(f"T4|{_iso()}|{time.time():.6f}|{cod}|{campo}|{valor}")


def log_t5(cod: str, campo: str, valor, idade_s, stale: bool):
    if not matches(cod, campo):
        return
    idade = "NA" if idade_s is None else f"{idade_s:.3f}"
    _write(f"T5|{_iso()}|{time.time():.6f}|{cod}|{campo}|{valor}|{idade}|{int(stale)}")


def log_consumo(uc: str, codigos: set[str], source):
    """T5 no ponto de consumo direto de um use case (BOX4P/PUT_RATIO/MPP etc.).

    Registra para cada chave traçada (e só para ela) o valor + idade + flag stale
    no momento em que o use case lê a cotação da fonte. Não altera comportamento.
    Com SH_TRACE_CHAVE=* registra todos os códigos do use case, em todos os campos.
    """
    if not _ENABLED or not codigos or _expirado():
        return
    from src.domain.services.market_data_source import OPENFAST_FIELD_STR, FieldName
    campo_por_nome = {nome: campo for campo, nome in OPENFAST_FIELD_STR.items()}
    if _WILDCARD:
        alvos = [(c.upper(), nome) for c in codigos for nome in campo_por_nome]
    else:
        alvos = [(codigo, nome) for codigo, nome in _TRAced if codigo in codigos]
    for codigo, nome in alvos:
        campo = campo_por_nome.get(nome)
        if campo is None:
            continue
        try:
            valor = source.ler_campo_cache(codigo, campo, allow_stale=True)
        except Exception:
            continue
        if valor is None:
            continue
        idade = None
        stale = False
        try:
            idade = source.get_idade_campo(codigo, campo)
        except Exception:
            pass
        try:
            stale = source.is_stale_campo(codigo, campo)
        except Exception:
            pass
        idade_s = "NA" if idade is None else f"{idade:.3f}"
        _write(f"T5|{_iso()}|{time.time():.6f}|{codigo}|{nome}|{valor}|{idade_s}|{int(stale)}|{uc}")


def log_t6(ctx: str, elapsed_s: float, flush: bool = False):
    _write(f"T6|{_iso()}|{time.time():.6f}|{ctx}|{elapsed_s:.6f}", forcar_flush=flush)


def log_evento(tipo: str, detalhe: str = "", flush: bool = False):
    _evt(tipo, detalhe, flush=flush)


def flush():
    with _lock:
        _flush()
