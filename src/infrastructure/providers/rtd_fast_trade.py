import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_ERRO_CELULA = "#"
_TOPIC_PATTERNS = [
    ("sqt", lambda c: ["SQT", c]),
    ("codigo", lambda c: [c]),
]
_CAMPOS_SONDA = ("PEX", "LAST", "BID", "ASK")
_CODIGOS_SONDA = ("PETR4", "VALE3", "ITUB4", "BBAS3")


def _formula_rtd(progid: str, *topicos: str) -> str:
    args = ",".join(f'"{t}"' for t in topicos)
    return f'=RTD("{progid}",,{args})'
_CHUNK_LINHAS = 256
_THROTTLE_DEFAULT_MS = 250


class RTDFastTrade:
    """Ponte Fast Trade -> Excel headless -> =RTD("srv.rtd").

    Abre o Excel sob demanda (primeira leitura/registro), grava formulas
    =RTD() em uma planilha oculta em blocos, faz refresh lendo a matriz
    inteira via Range.Value e mantem cache local + timestamps por tick."""

    suporta_push: bool = False
    suporta_cab_skip: bool = True

    def __init__(self, progid_rtd: str = "srv.rtd", throttle_ms: int = 200):
        self._progid = progid_rtd
        self._throttle_ms = int(throttle_ms) or _THROTTLE_DEFAULT_MS
        self._excel = None
        self._wb = None
        self._ws = None
        self._pid_excel: int | None = None
        self._hwnd: int | None = None
        self._lock = threading.Lock()

        self._subs: list[tuple[str, str]] = []
        self._pendentes: dict[str, str] = {}
        self._pos: dict[str, tuple[int, int]] = {}
        self._pos_rev: dict[tuple[int, int], str] = {}
        self._col_por_campo: dict[str, int] = {}
        self._campo_por_col: dict[int, str] = {}
        self._linha_por_cod: dict[str, int] = {}
        self._cache: dict[str, object] = {}
        self._cache_ts: dict[str, float] = {}

        self._topico_fn = _TOPIC_PATTERNS[0][1]  # SQT (nativo Fast Trade)
        self._throttle_orig_com: int | None = None
        self._throttle_orig_reg: int | None = None
        self._mudou_throttle = False
        self._attempted_abrir = False
        self._ultimo_bom = 0.0

    # ------------------------------------------------------------------ #
    # Abrir / fechar
    # ------------------------------------------------------------------ #
    @property
    def disponivel(self) -> bool:
        if self._excel is None:
            return False
        # Expira se ninguém leu o Excel recentemente (conexão morta).
        return (time.time() - self._ultimo_bom) < 20.0

    def _pids_excel(self) -> set[int]:
        try:
            import psutil
        except Exception:
            return set()
        try:
            return {
                p.pid for p in psutil.process_iter(["name"])
                if p.info["name"] and p.info["name"].lower() == "excel.exe"
            }
        except Exception:
            return set()

    def _caminhos_excel_options(self):
        for versao in ("16.0", "15.0", "14.0", "12.0"):
            yield versao, rf"Software\Microsoft\Office\{versao}\Excel\Options"

    def _ler_throttle_registro(self) -> int | None:
        import winreg
        for _, chave in self._caminhos_excel_options():
            try:
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, chave,
                        0, winreg.KEY_READ) as reg:
                    val, _ = winreg.QueryValueEx(reg, "RTDThrottleInterval")
                    return int(val)
            except OSError:
                continue
        return None

    def _salvar_throttle_registro(self, ms: int) -> bool:
        import winreg
        for _, chave in self._caminhos_excel_options():
            try:
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, chave,
                        0, winreg.KEY_SET_VALUE) as reg:
                    winreg.SetValueEx(reg, "RTDThrottleInterval", 0,
                                      winreg.REG_DWORD, int(ms))
                    return True
            except OSError:
                continue
        return False

    def _apagar_throttle_registro(self):
        import winreg
        for _, chave in self._caminhos_excel_options():
            try:
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, chave,
                        0, winreg.KEY_SET_VALUE) as reg:
                    try:
                        winreg.DeleteValue(reg, "RTDThrottleInterval")
                    except OSError:
                        pass
            except OSError:
                continue

    def _configurar_throttle(self, intervalo_ms: int = _THROTTLE_DEFAULT_MS):
        try:
            self._throttle_orig_com = int(self._excel.RTD.ThrottleInterval)
        except Exception:
            self._throttle_orig_com = None
        self._throttle_orig_reg = self._ler_throttle_registro()
        try:
            self._excel.RTD.ThrottleInterval = intervalo_ms
            self._mudou_throttle = True
        except Exception as e:
            logger.warning("ThrottleInterval via COM falhou: %s", e)
            self._salvar_throttle_registro(intervalo_ms)
            self._mudou_throttle = True

    def _restaurar_throttle(self):
        if not self._mudou_throttle or self._excel is None:
            return
        try:
            self._excel.RTD.ThrottleInterval = (
                self._throttle_orig_com or 2000)
        except Exception:
            pass
        reg_orig = self._throttle_orig_reg
        if reg_orig is None:
            self._apagar_throttle_registro()
        else:
            self._salvar_throttle_registro(reg_orig)
        self._mudou_throttle = False

    def _abrir(self) -> bool:
        if self._excel is not None:
            return True
        try:
            import win32com.client

            pids_antes = self._pids_excel()
            self._excel = win32com.client.DispatchEx("Excel.Application")
            xl = self._excel
            xl.Visible = False
            xl.DisplayAlerts = False
            xl.ScreenUpdating = False
            xl.EnableEvents = False
            xl.UserControl = False
            try:
                self._hwnd = int(xl.Hwnd)
            except Exception:
                self._hwnd = None

            novos = self._pids_excel() - pids_antes
            if novos:
                self._pid_excel = min(novos)

            self._wb = xl.Workbooks.Add()
            self._ws = self._wb.Worksheets(1)

            self._sondar_topico()
            self._configurar_throttle(self._throttle_ms)

            self._ultimo_bom = time.time()
            return True
        except Exception as e:
            logger.warning("Fast Trade RTD indisponivel: %s", e)
            self._fechar_excel_limpo()
            self._excel = None
            return False

    def _fechar_excel_limpo(self):
        wb = self._wb
        excel = self._excel
        if wb is not None:
            try:
                wb.Close(SaveChanges=False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
        pid = self._pid_excel
        if pid is not None:
            try:
                import psutil
                try:
                    p = psutil.Process(pid)
                    if p.is_running():
                        p.kill()
                except Exception:
                    pass
            except Exception:
                pass
        self._wb = None
        self._ws = None
        self._excel = None
        self._pid_excel = None
        self._hwnd = None

    # ------------------------------------------------------------------ #
    # Tópico
    # ------------------------------------------------------------------ #
    def _escrever_formulas(
            self, codigos: list[str], campos: list[str],
            fn_padrao, inicio: int) -> None:
        ws = self._ws
        ncols = len(campos)
        for i in range(0, len(codigos), _CHUNK_LINHAS):
            chunk = codigos[i:i + _CHUNK_LINHAS]
            formulas = []
            for cod in chunk:
                topicos = fn_padrao(cod)
                formulas.append(
                    [_formula_rtd(self._progid, *topicos, f)
                     for f in campos]
                )
            rng = ws.Range(
                ws.Cells(inicio + i, 1),
                ws.Cells(inicio + i + len(chunk) - 1, ncols),
            )
            try:
                rng.Formula = formulas
                continue
            except Exception:
                pass
            ws_c = ws.Cells
            for r_local, row_forms in enumerate(formulas):
                ln = inicio + i + r_local
                ws_c(ln, 1).Range(
                    ws_c(ln, 1), ws_c(ln, ncols)).Formula = row_forms

    def _ler_range(self, inicio: int, n_linhas: int, n_cols: int):
        rng = self._ws.Range(
            self._ws.Cells(inicio, 1),
            self._ws.Cells(inicio + n_linhas - 1, n_cols),
        )
        return rng.Value

    def _sondar_topico(self):
        melhor_fn = None
        melhor_vivos = -1
        base = 900000
        for i, (nome, fn) in enumerate(_TOPIC_PATTERNS):
            inicio = base + i * 700
            try:
                self._escrever_formulas(
                    list(_CODIGOS_SONDA), list(_CAMPOS_SONDA), fn,
                    inicio=inicio)
            except Exception as e:
                logger.debug("Fast Trade sonda[%s] falhou: %s", nome, e)
                continue
            time.sleep(0.4)
            arr = self._ler_range(inicio, len(_CODIGOS_SONDA),
                                  len(_CAMPOS_SONDA))
            _, vivas = self._contar(arr)
            if vivas > melhor_vivos:
                melhor_vivos = vivas
                melhor_fn = fn
        if melhor_fn is None or melhor_vivos <= 0:
            logger.info("Fast Trade: nenhum topico retornou dados — "
                        "usando SQT (FastTrade fechado / fora do horario?)")
            melhor_fn = _TOPIC_PATTERNS[0][1]
        self._topico_fn = melhor_fn

    def _contar(self, arr) -> tuple[int, int]:
        if arr is None:
            return 0, 0
        if not isinstance(arr, (tuple, list)):
            arr = (arr,)
        nums = 0
        vivas = 0
        for linha in arr:
            if not isinstance(linha, (tuple, list)):
                linha = (linha,)
            for v in linha:
                try:
                    f = float(str(v).replace(",", "."))
                except (ValueError, TypeError):
                    continue
                nums += 1
                if f > 0:
                    vivas += 1
        return nums, vivas

    # ------------------------------------------------------------------ #
    # Registro de tópicos
    # ------------------------------------------------------------------ #
    def registrar_topico(self, codigo: str, campo: str) -> int:
        if not campo:
            return -1
        codigo = codigo.upper()
        campo = campo.upper()
        chave = f"{codigo}|{campo}"
        with self._lock:
            if chave not in self._pendentes and chave not in self._pos:
                self._pendentes[chave] = campo
            if (codigo, campo) not in self._subs:
                self._subs.append((codigo, campo))
        return 0

    def registrar_lista(self, registros: list[tuple[str, str]]) -> int:
        count = 0
        for codigo, campo in registros:
            if self.registrar_topico(codigo, campo) >= 0:
                count += 1
        return count

    def registrar_status(self, codigo: str) -> int:
        return self.registrar_topico(codigo, "ST")

    def _aplicar_pendentes(self) -> None:
        with self._lock:
            if not self._pendentes:
                return
            pendentes = dict(self._pendentes)
            self._pendentes.clear()
        novas_linhas: list[int] = []
        with self._lock:
            for chave, campo in pendentes.items():
                if chave in self._pos:
                    continue
                codigo = chave.split("|", 1)[0]
                col = self._col_por_campo.get(campo)
                if col is None:
                    col = len(self._col_por_campo) + 1
                    self._col_por_campo[campo] = col
                    self._campo_por_col[col] = campo
                linha = self._linha_por_cod.get(codigo)
                if linha is None:
                    linha = (max(self._linha_por_cod.values(), default=1)
                             + 1)
                    self._linha_por_cod[codigo] = linha
                    novas_linhas.append(linha)
                self._pos[chave] = (linha, col)
                self._pos_rev[(linha, col)] = chave
        if not novas_linhas:
            return

        # Escreve as células para as novas linhas (restaurando as colunas já
        # registradas daquele código).
        campos_registrados_por_linha: dict[int, dict[str, str]] = {}
        with self._lock:
            for codigo, campo in self._subs:
                linha = self._linha_por_cod.get(codigo)
                if linha is None:
                    continue
                campos_registrados_por_linha.setdefault(linha, {})[campo] = codigo
        for inicio in range(0, len(novas_linhas), _CHUNK_LINHAS):
            chunk = novas_linhas[inicio:inicio + _CHUNK_LINHAS]
            ncols = len(self._col_por_campo)
            formulas = []
            for linha in chunk:
                row = [""] * ncols
                for campo, codigo in campos_registrados_por_linha.get(linha, {}).items():
                    col = self._col_por_campo.get(campo)
                    if col is None:
                        continue
                    topico = self._topico_fn(codigo)
                    if isinstance(topico, str):
                        topico = [topico]
                    row[col - 1] = _formula_rtd(self._progid, *topico, campo)
                formulas.append(row)
            rng = self._ws.Range(
                self._ws.Cells(min(chunk), 1),
                self._ws.Cells(max(chunk), ncols),
            )
            try:
                rng.Formula = formulas
            except Exception as e:
                logger.warning("Fast Trade: falha escrita formulas: %s", e)

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    def _ler_do_excel(self) -> None:
        with self._lock:
            if not self._linha_por_cod:
                return
            max_linha = max(self._linha_por_cod.values(), default=1)
            ncols = len(self._col_por_campo)
        agora = time.time()
        for inicio in range(2, max_linha + 1, _CHUNK_LINHAS):
            fim = min(inicio + _CHUNK_LINHAS - 1, max_linha)
            n_linhas = fim - inicio + 1
            try:
                arr = self._ler_range(inicio, n_linhas, ncols)
            except Exception:
                continue
            if arr is None:
                continue
            if not isinstance(arr, (tuple, list)):
                arr = (arr,)
            with self._lock:
                for r_local, linha in enumerate(arr):
                    if not isinstance(linha, (tuple, list)):
                        linha = (linha,)
                    for c_local, valor in enumerate(linha):
                        pos = (inicio + r_local, c_local + 1)
                        chave = self._pos_rev.get(pos)
                        if chave is None:
                            continue
                        if isinstance(valor, str) and valor.strip().startswith(_ERRO_CELULA):
                            continue
                        try:
                            v = float(str(valor).replace(",", "."))
                        except (ValueError, TypeError):
                            continue
                        if self._cache.get(chave) != v:
                            self._cache[chave] = v
                            self._cache_ts[chave] = agora
        self._ultimo_bom = time.time()

    def refresh(self, timeout_ms: int = 0) -> dict[str, object]:
        if not self.disponivel and not self._abrir():
            return {}
        self._aplicar_pendentes()
        try:
            self._excel.Calculate()
        except Exception:
            pass
        self._ler_do_excel()
        return {}

    def ler_campo_cache(self, codigo: str, campo: str) -> Optional[float]:
        chave = f"{codigo.upper()}|{campo.upper()}"
        with self._lock:
            raw = self._cache.get(chave)
        if raw is None:
            return None
        try:
            v = float(str(raw).replace(",", "."))
            return 0.0 if v == 0 else v
        except (ValueError, TypeError):
            return None

    def ler_campos(self, codigo: str, *campos: str) -> dict[str, float | None]:
        return {c: self.ler_campo_cache(codigo, c) for c in campos}

    def ler_status_cache(self, codigo: str) -> str:
        chave = f"{codigo.upper()}|ST"
        with self._lock:
            raw = self._cache.get(chave)
        if raw is None:
            return ""
        return str(raw).strip().upper()

    def forcar_leitura(self, codigo: str, campo: str) -> Optional[float]:
        codigo = codigo.upper()
        campo = campo.upper()
        chave = f"{codigo}|{campo}"
        with self._lock:
            pos = self._pos.get(chave)
            col = self._col_por_campo.get(campo)
        if pos is None or col is None or self._ws is None:
            return self.ler_campo_cache(codigo, campo)
        try:
            valor = self._ws.Cells(pos[0], pos[1]).Value
            if valor is None:
                return None
            v = float(str(valor).replace(",", "."))
            if v != 0:
                with self._lock:
                    self._cache[chave] = v
                    self._cache_ts[chave] = time.time()
                return v
            return 0.0
        except (ValueError, TypeError, Exception):
            return None

    def invalidar_cache(self, codigo: str, campo: str):
        chave = f"{codigo.upper()}|{campo.upper()}"
        with self._lock:
            self._cache.pop(chave, None)
            self._cache_ts.pop(chave, None)

    def get_ts_campo(self, codigo: str, campo: str) -> float | None:
        chave = f"{codigo.upper()}|{campo.upper()}"
        with self._lock:
            return self._cache_ts.get(chave)

    def get_idade_campo(self, codigo: str, campo: str) -> float | None:
        chave = f"{codigo.upper()}|{campo.upper()}"
        with self._lock:
            ts = self._cache_ts.get(chave)
        if ts is None:
            return None
        return time.time() - ts

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #
    def reconectar(self, max_attempts: int = 2, delay_s: float = 1.0) -> bool:
        self.desconectar()
        for tentativa in range(1, max_attempts + 1):
            if self._abrir():
                self.refresh(0)
                return True
            if tentativa < max_attempts:
                time.sleep(delay_s)
        return False

    def desconectar(self):
        try:
            self._restaurar_throttle()
        except Exception:
            pass
        self._fechar_excel_limpo()
        with self._lock:
            self._cache.clear()
            self._cache_ts.clear()
            self._pos.clear()
            self._pos_rev.clear()
            self._col_por_campo.clear()
            self._campo_por_col.clear()
            self._linha_por_cod.clear()
            self._pendentes.clear()
        self._attempted_abrir = False