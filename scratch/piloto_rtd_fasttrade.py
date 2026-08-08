"""
PILOTO ISOLADO — Ponte Excel headless <-> RTD Fast Trade (Cedro / srv.rtd).

ISOLADO E DESCARTÁVEL:
  - NAO importa de src/ (nada do Spreadhunter).
  - NAO toca em config/, banco, parametros, colunas nem UI.
  - Usa DispatchEx (instancia Excel NOVA e dedicada; nunca anexa numa existente).
  - Lifecycle 100% limpo: Quit() + kill por PID em finally, restaura Throttle e registro.

Pre-requisitos: Excel instalado, FastTrade/Cedro aberto e logado, mercado aberto
(seg-sex 10:00-17:00 horario de Brasilia). Fora de horario o piloto roda mas
"celulas vivas" = 0.

Uso:
  python scratch/piloto_rtd_fasttrade.py                       # default 2000 linhas, 15s manual + 15s auto
  python scratch/piloto_rtd_fasttrade.py --linhas 5000 --t-auto 30
  python scratch/piloto_rtd_fasttrade.py --padrao             # so descobre o padrao de topico e sai
  python scratch/piloto_rtd_fasttrade.py --codigos PETR4,VALE3,ITUB4 --linhas 100
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import winreg

import numpy as np
import pythoncom
import win32com.client
import win32process

try:
    import psutil
except Exception:
    psutil = None

# ------------------------------------------------------------------------- #
# Espelha src/domain/services (FASTTRADE_FIELD_STR / FASTRADE_SERVIDOR)
# ------------------------------------------------------------------------- #
PROGID_RTD = "srv.rtd"
FIELDS = [
    "PEX", "LAST", "BID", "ASK", "ST", "QTLAST", "VOLBID", "VOLASK",
    "CAB", "HIGH", "LOW", "OPEN", "CLOSE", "VOLQ", "VOLF", "VAR",
]

# Padroes candidatos de topico (o adapter atual usa "{codigo}_B_0")
TOPIC_PATTERNS = [
    ("codigo", lambda c: c),
    ("codigo_B_0", lambda c: f"{c}_B_0"),
    ("codigo_B", lambda c: f"{c}_B"),
]

DEFAULT_CODIGOS = [
    "PETR4", "VALE3", "ITUB4", "BBAS3", "B3SA3", "WEGE3", "ABEV3", "PETR3",
    "MGLU3", "BBDC4", "GGBR4", "JBSS3", "RENT3", "BRFS3", "RAIL3", "SUZB3",
]

XL_CALC_MANUAL = -4135
XL_CALC_AUTOMATIC = -4105
CHUNK_ROWS = 256              # linhas por bloco de escrita de formulas
CPU_AMOSTRA_INTERVALO = 1.0   # amostrar CPU/RAM a cada 1s


# ------------------------------------------------------------------------- #
# Helpers de conversao
# ------------------------------------------------------------------------- #
def _para_float(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def _contar(arr) -> tuple[int, int]:
    """Retorna (numeros, vivos>0). 'numeros' inclui zeros (conseguiu conectar)."""
    if arr is None or arr.size == 0:
        return 0, 0
    nums = 0
    vivos = 0
    for v in arr.flatten():
        if isinstance(v, str) and v.strip().startswith("#"):
            continue  # erro Excel (#N/A etc.)
        try:
            f = _para_float(v)
        except Exception:
            continue
        nums += 1
        if f > 0:
            vivos += 1
    return nums, vivos


def _media(v: list[float]) -> float:
    return sum(v) / len(v) if v else 0.0


# ------------------------------------------------------------------------- #
# Registro / ThrottleRTD
# ------------------------------------------------------------------------- #
def _caminhos_excel_options():
    for versao in ("16.0", "15.0", "14.0", "12.0"):
        yield versao, rf"Software\Microsoft\Office\{versao}\Excel\Options"


def ler_throttle_registro() -> int | None:
    for _, chave in _caminhos_excel_options():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave,
                                0, winreg.KEY_READ) as reg:
                val, _ = winreg.QueryValueEx(reg, "RTDThrottleInterval")
                return int(val)
        except OSError:
            continue
    return None


def salvar_throttle_registro(ms: int) -> bool:
    for _, chave in _caminhos_excel_options():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave,
                                0, winreg.KEY_SET_VALUE) as reg:
                winreg.SetValueEx(reg, "RTDThrottleInterval", 0,
                                  winreg.REG_DWORD, int(ms))
                return True
        except OSError:
            continue
    return False


def apagar_throttle_registro():
    for _, chave in _caminhos_excel_options():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave,
                                0, winreg.KEY_SET_VALUE) as reg:
                try:
                    winreg.DeleteValue(reg, "RTDThrottleInterval")
                except OSError:
                    pass
        except OSError:
            continue


# ------------------------------------------------------------------------- #
# Piloto
# ------------------------------------------------------------------------- #
class PilotoRTDFastTrade:
    def __init__(self, codigos: list[str], t_manual: float, t_auto: float):
        self.codigos = codigos
        self.t_manual = t_manual
        self.t_auto = t_auto
        self.excel = None
        self.wb = None
        self.ws = None
        self.pid_excel: int | None = None
        self.hwnd: int | None = None
        self.throttle_original_com: int | None = None
        self.throttle_original_reg: int | None = None
        self.mudou_throttle = False

    # ------------------------------------------------------------------ #
    def _pids_excel_atuais(self) -> set[int]:
        if psutil is None:
            return set()
        try:
            return {
                p.pid for p in psutil.process_iter(["name"])
                if p.info["name"] and p.info["name"].lower() == "excel.exe"
            }
        except Exception:
            return set()

    def abrir(self):
        pids_antes = self._pids_excel_atuais()
        try:
            self.excel = win32com.client.DispatchEx("Excel.Application")
        except Exception as e:
            print(f"Falha ao abrir Excel via DispatchEx: {e}")
            raise
        xl = self.excel
        xl.Visible = False
        xl.DisplayAlerts = False
        xl.ScreenUpdating = False
        xl.EnableEvents = False
        xl.UserControl = False
        try:
            self.hwnd = int(xl.Hwnd)
        except Exception:
            self.hwnd = None

        # PID da instancia nova (diff sobre o conjunto anterior)
        novos = self._pids_excel_atuais() - pids_antes
        if novos:
            self.pid_excel = min(novos)
        if self.pid_excel is None:
            try:
                if self.hwnd:
                    _, pid = win32process.GetWindowThreadProcessId(self.hwnd)
                    self.pid_excel = int(pid)
            except Exception:
                pass
        return xl

    def _configurar_throttle(self, intervalo_ms: int = 250):
        try:
            self.throttle_original_com = int(
                self.excel.RTD.ThrottleInterval)
        except Exception:
            self.throttle_original_com = None
        self.throttle_original_reg = ler_throttle_registro()
        try:
            self.excel.RTD.ThrottleInterval = intervalo_ms
            self.mudou_throttle = True
        except Exception as e:
            print(f"[aviso] ThrottleInterval via COM falhou: {e}")
            salvar_throttle_registro(intervalo_ms)
            self.mudou_throttle = True

    def _restaurar_throttle(self):
        if not self.mudou_throttle or self.excel is None:
            return
        try:
            self.excel.RTD.ThrottleInterval = (
                self.throttle_original_com or 2000)
        except Exception:
            pass
        if self.throttle_original_reg is None:
            apagar_throttle_registro()
        else:
            salvar_throttle_registro(self.throttle_original_reg)

    def fechar(self):
        try:
            if self.wb is not None:
                try:
                    self.wb.Close(SaveChanges=False)
                except Exception:
                    pass
            if self.excel is not None:
                try:
                    self.excel.Quit()
                except Exception:
                    pass
        finally:
            if self.pid_excel is not None and psutil is not None:
                try:
                    p = psutil.Process(self.pid_excel)
                    if p.is_running():
                        p.terminate()
                        try:
                            p.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            p.kill()
                except psutil.NoSuchProcess:
                    pass
                except Exception:
                    pass
            self.excel = None
            self.wb = None
            self.ws = None

    # ----------------------------------------------------------------- #
    def planilha(self):
        self.wb = self.excel.Workbooks.Add()
        self.ws = self.wb.Worksheets(1)
        return self.ws

    def escrever_matriz(self, codigos, campos, fn_padrao, inicio=1):
        """Grava formulas =RTD() em blocos (1 chamada COM por chunk).
        Nao itera celula-a-celula."""
        t0 = time.perf_counter()
        n = len(codigos)
        ncols = len(campos)
        for i in range(0, n, CHUNK_ROWS):
            chunk = codigos[i:i + CHUNK_ROWS]
            formulas = []
            for cod in chunk:
                topico = fn_padrao(cod)
                formulas.append(
                    [f"=RTD(\"{PROGID_RTD}\",,\"{topico}\",\"{f}\")"
                     for f in campos]
                )
            rng = self.ws.Range(
                self.ws.Cells(inicio + i, 1),
                self.ws.Cells(inicio + i + len(chunk) - 1, ncols),
            )
            ok = False
            try:
                rng.Formula = formulas   # 1 atribuicao VARANT array
                ok = True
            except Exception:
                pass
            if not ok:
                # fallback: escreve linha a linha (Formula, nao Value)
                ws_c = self.ws.Cells
                for r_local, row_forms in enumerate(formulas):
                    ln = inicio + i + r_local
                    ws_c(ln, 1).Range(ws_c(ln, 1),
                                      ws_c(ln, ncols)).Formula = row_forms
        dt = time.perf_counter() - t0
        print(f"[info] escritas {n}x{ncols} formulas em {dt:.3f}s")
        return dt

    def ler_bloco(self, inicio, n_linhas, n_cols):
        rng = self.ws.Range(
            self.ws.Cells(inicio, 1),
            self.ws.Cells(inicio + n_linhas - 1, n_cols),
        )
        t0 = time.perf_counter()
        raw = rng.Value          # 1 chamada COM so
        t_read = time.perf_counter() - t0
        t0 = time.perf_counter()
        arr = np.array(raw, dtype=object) if raw is not None else None
        t_np = time.perf_counter() - t0
        return arr, t_read, t_np

    # ------------------------------------------------------------------ #
    def loop(self, n_linhas, n_cols, segundos: float, rotulo: str) -> dict:
        n_reads = 0
        soma_read = 0.0
        soma_np = 0.0
        max_read = 0.0
        max_np = 0.0
        vivas_min: int | None = None
        vivas_max: int | None = None
        cpu_py: list[float] = []
        cpu_ex: list[float] = []
        rss_py: list[float] = []
        rss_ex: list[float] = []
        t_fim = time.time() + segundos
        t_prox_amostra = time.time()
        while time.time() < t_fim:
            arr, t_read, t_np = self.ler_bloco(2, n_linhas, n_cols)
            n_reads += 1
            soma_read += t_read
            soma_np += t_np
            max_read = max(max_read, t_read)
            max_np = max(max_np, t_np)
            if arr is not None:
                _, vivas = _contar(arr)
                if arr.size > 0:
                    vivas_min = vivas if vivas_min is None else min(vivas_min, vivas)
                    vivas_max = vivas if vivas_max is None else max(vivas_max, vivas)
            agora = time.time()
            if agora >= t_prox_amostra:
                t_prox_amostra = agora + CPU_AMOSTRA_INTERVALO
                if psutil is not None:
                    try:
                        p = psutil.Process(os.getpid())
                        cpu_py.append(p.cpu_percent(None))
                        rss_py.append(p.memory_info().rss / (1024 ** 2))
                    except Exception:
                        pass
                    if self.pid_excel is not None:
                        try:
                            pe = psutil.Process(self.pid_excel)
                            cpu_ex.append(pe.cpu_percent(None))
                            rss_ex.append(pe.memory_info().rss / (1024 ** 2))
                        except Exception:
                            pass
        t_inicio = t_fim - segundos
        dur = time.time() - t_inicio
        return {
            "rotulo": rotulo,
            "reads": n_reads,
            "fps": n_reads / dur if dur else 0.0,
            "media_read_ms": (soma_read / n_reads) * 1000 if n_reads else 0.0,
            "max_read_ms": max_read * 1000,
            "media_np_ms": (soma_np / n_reads) * 1000 if n_reads else 0.0,
            "max_np_ms": max_np * 1000,
            "vivas_min": vivas_min,
            "vivas_max": vivas_max,
            "cpu_py": _media(cpu_py),
            "cpu_ex": _media(cpu_ex),
            "rss_py_mb": _media(rss_py),
            "rss_ex_mb": _media(rss_ex),
        }

    # ------------------------------------------------------------------ #
    def descobrir_padrao(self, codes) -> callable | None:
        melhor_fn = None
        melhor_vivos = -1
        print("--- descoberta de topico (4 codigos x 4 campos) ---")
        for pos, (nome, fn) in enumerate(TOPIC_PATTERNS):
            ini = (len(codes) + 2) * pos + 2
            campos_teste = FIELDS[:4]
            self.escrever_matriz(codes, campos_teste, fn, inicio=ini)
            time.sleep(1.5)
            arr, _, _ = self.ler_bloco(ini, len(codes), len(campos_teste))
            nums, vivas = _contar(arr) if arr is not None else (0, 0)
            print(f"  [{nome}]: numeros={nums} vivos={vivas}")
            if vivas > melhor_vivos:
                melhor_vivos = vivas
                melhor_fn = fn
        if melhor_fn is None or melhor_vivos <= 0:
            print("[aviso] nenhum padrao retornou dados vivos -> usando o "
                  "primeiro padrao para nao quebrar o benchmark "
                  "(Fortrade fechado ou fora do horario?)")
            melhor_fn = TOPIC_PATTERNS[0][1]
        return melhor_fn

    # ------------------------------------------------------------------ #
    def executar(self, so_padrao: bool = False) -> int:
        try:
            self.abrir()
        except Exception as e:
            print(f"Falha ao abrir Excel/COM: {e}")
            return 2
        print(f"[excel] PID={self.pid_excel} HWND={self.hwnd}")
        try:
            self._configurar_throttle(250)
        except Exception as e:
            print(f"[aviso] throttle: {e}")

        try:
            self.planilha()
            fn_padrao = self.descobrir_padrao(self.codigos[:4])
            print(f"[padrao escolhido]: {fn_padrao}")
            if so_padrao:
                return 0

            codes = self.codigos
            ncols = len(FIELDS)
            self.escrever_matriz(codes, FIELDS, fn_padrao, inicio=2)
            time.sleep(2.0)

            resultados = []
            if self.t_manual > 0:
                try:
                    self.excel.Calculation = XL_CALC_MANUAL
                except Exception:
                    pass
                time.sleep(0.5)
                resultados.append(
                    self.loop(len(codes), ncols, self.t_manual, "Manual"))

            if self.t_auto > 0:
                try:
                    self.excel.Calculation = XL_CALC_AUTOMATIC
                except Exception:
                    pass
                time.sleep(0.5)
                resultados.append(
                    self.loop(len(codes), ncols, self.t_auto, "Automatic"))

            self._imprimir(resultados)
            return 0
        finally:
            try:
                self._restaurar_throttle()
            except Exception:
                pass
            self.fechar()
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    def _imprimir(self, resultados: list[dict]):
        print("\n=== BENCHMARK ===")
        for r in resultados:
            print(f"\n[{r['rotulo']}] {r['reads']} leituras | FPS={r['fps']:.1f}")
            print(f"  Range.Value  : media {r['media_read_ms']:.2f} ms | "
                  f"max {r['max_read_ms']:.2f} ms")
            print(f"  -> np.array  : media {r['media_np_ms']:.2f} ms | "
                  f"max {r['max_np_ms']:.2f} ms")
            print(f"  celulas vivas (min-max): {r['vivas_min']} - {r['vivas_max']}")
            print(f"  CPU app={r['cpu_py']:.1f}% Excel={r['cpu_ex']:.1f}%  "
                  f"RAM app={r['rss_py_mb']:.0f}MB Excel={r['rss_ex_mb']:.0f}MB")


# ------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(
        description="Piloto RTD Fast Trade via Excel headless (isolado)")
    parser.add_argument("--linhas", type=int, default=2000)
    parser.add_argument("--t-manual", type=int, default=15)
    parser.add_argument("--t-auto", type=int, default=15)
    parser.add_argument("--padrao", action="store_true",
                        help="somente descobrir o padrao de topico e sair")
    parser.add_argument("--codigos", type=str, default=None,
                        help="codigos separados por virgula")
    args = parser.parse_args()

    if args.codigos:
        cods = [c.strip().upper() for c in args.codigos.split(",") if c.strip()]
    else:
        cods = DEFAULT_CODIGOS
        while len(cods) < args.linhas:
            cods += DEFAULT_CODIGOS
        cods = cods[: args.linhas]

    p = PilotoRTDFastTrade(codigos=cods, t_manual=args.t_manual,
                           t_auto=args.t_auto)
    code = p.executar(so_padrao=args.padrao)
    sys.exit(code or 0)


if __name__ == "__main__":
    main()