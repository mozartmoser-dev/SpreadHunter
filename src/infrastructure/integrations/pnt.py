import ctypes
import pyautogui
import pyperclip
import time
import logging
from pathlib import Path

try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    from src.application.dtos.dtos import OportunidadeMonitor
except ImportError:
    OportunidadeMonitor = None

PYNT_TITLES = ["PlugNTrade", "PlugAndTrade", "Plug & Trade", "FastTrader", "PnT_FastTrader"]

logger = logging.getLogger(__name__)

class PNTScreenManager:
    """Gerenciador de telas do PNT via reconhecimento de imagem"""
    
    def __init__(self):
        self.screens_dir = Path("scratch/pnt_screens")
        self.screens_dir.mkdir(exist_ok=True)
        
    def find_pnt_window(self):
        """Encontra e foca a janela do PNT usando Win32 API (ou fallback pyautogui)."""
        if HAS_WIN32:
            return self._find_pnt_window_win32()
        return self._find_pnt_window_pyautogui()

    def _find_pnt_window_win32(self):
        try:
            target_hwnd = [0]

            def enum_callback(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd)
                for t in PYNT_TITLES:
                    if t.lower() in title.lower():
                        target_hwnd[0] = hwnd
                        return False
                return True

            win32gui.EnumWindows(enum_callback, None)

            hwnd = target_hwnd[0]
            if hwnd:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
                time.sleep(1.0)
                logger.info("PNT focado com sucesso (Win32)!")
                return True
            else:
                logger.warning("Nenhuma janela do PNT encontrada")
                return False
        except Exception as e:
            logger.warning("Erro ao focar PNT (Win32): %s", e)
            return False

    def _find_pnt_window_pyautogui(self):
        try:
            win = None
            for t in PYNT_TITLES:
                wins = pyautogui.getWindowsWithTitle(t)
                if wins:
                    win = wins[0]
                    break

            if win:
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(1.0)
                logger.info("PNT focado com sucesso (pyautogui)!")
                return True
            else:
                logger.warning("Nenhuma janela do PNT encontrada")
                return False
        except Exception as e:
            logger.warning("Erro ao focar PNT (pyautogui): %s", e)
            return False
    
    def open_multileg_screen(self):
        """Abre a tela MultiLeg manualmente (usuário deve fazer isso)"""
        logger.info("Por favor, abra manualmente a tela MultiLeg no PNT...")
        time.sleep(2)
        return self.find_pnt_window()
    
    def open_spread_screen(self):
        """Abre a tela Spread manualmente (usuário deve fazer isso)"""
        logger.info("Por favor, abra manualmente a tela Spread no PNT...")
        time.sleep(2)
        return self.find_pnt_window()

_PNT_WINDOW_TITLES = [
    "FastTrader - Plug and Trade",
    "FastTrader",
    "PlugNTrade",
    "PlugAndTrade",
    "Plug & Trade",
    "PnT_FastTrader",
]

# Títulos usados para clique/teclado (pygetwindow)
_PNT_SEARCH_TITLES = [
    "Plug and Trade",
    "FastTrader",
    "PlugNTrade",
    "PlugAndTrade",
    "Plug & Trade",
    "PnT_FastTrader",
]

def _localizar_imagem(images_dir: str, nome: str, confidence: float = 0.7, region: tuple | None = None) -> tuple[int, int, int, int] | None:
    """Tenta locateOnScreen; retorna None se não achar."""
    try:
        path = Path(images_dir) / nome
        if not path.exists():
            logger.warning("Imagem não encontrada: %s", path)
            return None
        result = pyautogui.locateOnScreen(str(path), confidence=confidence, region=region)
        if result is None:
            logger.info("Imagem '%s' não corresponde à tela", nome)
        return result
    except Exception as e:
        logger.warning("Erro ao localizar imagem '%s': %s", nome, e or "(sem detalhes)")
        return None

def _achar_janela_pnt() -> int | None:
    """Localiza o HWND da janela principal do PNT (prefere janela maior)."""
    try:
        import win32gui
        for t in _PNT_WINDOW_TITLES:
            hwnd = win32gui.FindWindow(None, t)
            if hwnd:
                return hwnd
        found = {}
        def enum_windows(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            for pat in _PNT_WINDOW_TITLES:
                if pat.lower() in title.lower():
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        area = (rect[2] - rect[0]) * (rect[3] - rect[1])
                        found[hwnd] = area
                    except Exception:
                        pass
                    break
            return True
        win32gui.EnumWindows(enum_windows, None)
        if found:
            return max(found, key=found.get)
        return None
    except Exception as e:
        logger.warning("_achar_janela_pnt falhou: %s", e)
        return None


def _achar_janela_pnt_por_processo() -> int | None:
    """Localiza HWND do PNT pelo nome do processo PnT.Inteface.exe."""
    try:
        import psutil
        import win32gui
        import win32process

        pids = set()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                nome = (proc.info['name'] or '').lower()
                if nome in ('pnt.interface.exe', 'pnt.inteface.exe', 'fasttrader.exe'):
                    pids.add(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if not pids:
            return None

        found = {}
        def enum_windows(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in pids:
                    rect = win32gui.GetWindowRect(hwnd)
                    area = (rect[2] - rect[0]) * (rect[3] - rect[1])
                    found[hwnd] = area
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum_windows, None)
        if found:
            return max(found, key=found.get)
        return None
    except Exception as e:
        logger.warning("_achar_janela_pnt_por_processo falhou: %s", e)
        return None


def _achar_combobox(hwnd_pai: int) -> tuple[int, tuple[int, int, int, int]] | None:
    """Localiza o ComboBox visível dentro do dialog 'Importação de Basket'."""
    try:
        import win32gui
        import win32con

        # 1. Encontra a janela do dialog 'Importação de Basket'
        hwnd_dialog = [0]
        def enum_windows(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "importação de basket" in title.lower():
                    owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
                    if owner == hwnd_pai or hwnd_pai is None:
                        hwnd_dialog[0] = hwnd
                        return False
            return True
        win32gui.EnumWindows(enum_windows, None)

        if not hwnd_dialog[0]:
            # Fallback: procura qualquer janela visível com o título no sistema
            def enum_windows_fallback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "importação de basket" in title.lower():
                        hwnd_dialog[0] = hwnd
                        return False
                return True
            win32gui.EnumWindows(enum_windows_fallback, None)

        if not hwnd_dialog[0]:
            logger.info("Dialog 'Importação de Basket' não encontrado no Windows")
            return None

        logger.info("Dialog 'Importação de Basket' encontrado (HWND: %s)", hwnd_dialog[0])

        # 2. Encontra o ComboBox "Tipo de Ordem"
        #    Há 4 combos: Formato(y=700), Arredondar(y=724), Tipo de Ordem(y=675), Quantidade(y=749)
        #    "Tipo de Ordem" é o mais ao topo (menor y).
        resultados = []
        def enum_child(hwnd, _):
            cls = win32gui.GetClassName(hwnd).lower()
            if "combo" in cls and win32gui.IsWindowVisible(hwnd):
                rect = win32gui.GetWindowRect(hwnd)
                if (rect[2] - rect[0]) > 50:
                    resultados.append((hwnd, rect))
            return True

        win32gui.EnumChildWindows(hwnd_dialog[0], enum_child, None)
        if resultados:
            resultados.sort(key=lambda r: r[1][1])
            hwnd_combo, rect_combo = resultados[0]
            logger.info("ComboBox 'Tipo de Ordem' encontrado (HWND: %s, Rect: %s)", hwnd_combo, rect_combo)
            return (hwnd_combo, rect_combo)
        else:
            logger.warning("Nenhum ComboBox encontrado dentro do dialog 'Importação de Basket'")
            return None
    except Exception as e:
        logger.error("Erro ao procurar ComboBox no dialog: %s", e)
        return None


def _selecionar_item_combobox(hwnd_combo: int, texto: str, rect: tuple) -> bool:
    """Seleciona item no ComboBox via clique na seta + navegação por teclado.

    CB_FINDSTRINGEXACT é usado apenas para obter o índice (consulta pura).
    A seleção real é feita clicando na seta da direita do ComboBox (para garantir
    que a lista abra) e enviando comandos de teclado (Home, Down×N, Enter).
    """
    try:
        import win32gui
        import win32con

        # Descobre o índice do item alvo (consulta pura, não altera estado)
        index_alvo = win32gui.SendMessage(hwnd_combo, win32con.CB_FINDSTRINGEXACT, -1, texto)
        encontrou = index_alvo != win32con.CB_ERR
        if encontrou:
            logger.info("Item '%s' encontrado no índice %d", texto, index_alvo)
        else:
            logger.warning("CB_FINDSTRINGEXACT falhou (cross-process), fallback digitação")

        # Seta foco via win32
        try:
            win32gui.SetFocus(hwnd_combo)
            time.sleep(0.1)
        except Exception:
            pass

        # Clica na seta direita do dropdown para abrir a lista visualmente
        seta_x = rect[2] - 10
        seta_y = (rect[1] + rect[3]) // 2
        pyautogui.moveTo(seta_x, seta_y, duration=0.15)
        pyautogui.click()
        time.sleep(0.5)

        if encontrou:
            # Navega com teclado até o índice
            pyautogui.press("home")
            time.sleep(0.2)
            for _ in range(index_alvo):
                pyautogui.press("down")
                time.sleep(0.1)
            pyautogui.press("enter")
        else:
            # Fallback: digita o texto p/ autocomplete selecionar
            pyautogui.write(texto, interval=0.06)
            time.sleep(0.5)
            pyautogui.press("enter")
        time.sleep(0.5)

        # Tenta verificar (não crítica)
        try:
            cur = win32gui.SendMessage(hwnd_combo, win32con.CB_GETCURSEL, 0, 0)
            if encontrou and cur == index_alvo:
                logger.info("Seleção confirmada: índice %d = '%s'", cur, texto)
        except Exception:
            pass
        return True

    except Exception as e:
        logger.warning("Erro ao selecionar item via teclado: %s", e)
        return False



def _focar_janela_pnt() -> bool:
    """Localiza e ativa a janela do PNT: processo > título."""
    try:
        # 1. Processo PnT.Inteface.exe (não depende de título)
        hwnd = _achar_janela_pnt_por_processo()
        if hwnd:
            import win32gui
            import win32con
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.5)
            try:
                ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
            except Exception as e:
                logger.warning("SwitchToThisWindow falhou: %s", e)
            rect = win32gui.GetWindowRect(hwnd)
            if rect:
                pyautogui.click((rect[0] + rect[2]) // 2, rect[1] + 15)
                time.sleep(0.5)
                logger.info("PNT focado por processo (SwitchToThisWindow + click)!")
                return True
            return False

        # 2. Fallback: título (Win32)
        if HAS_WIN32:
            import win32gui
            import win32con
            hwnd = _achar_janela_pnt()
            if hwnd:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                try:
                    ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
                except Exception as e:
                    logger.warning("SwitchToThisWindow falhou: %s", e)
                time.sleep(1.5)
                logger.info("PNT focado por título (Win32)!")
                return True

        # 3. Último fallback: pygetwindow
        import pygetwindow as gw
        for pattern in _PNT_SEARCH_TITLES:
            windows = gw.getWindowsWithTitle(pattern)
            if windows:
                w = windows[0]
                if w.isMinimized:
                    w.restore()
                try:
                    w.activate()
                except Exception as e:
                    logger.warning("activate falhou: %s", e)
                time.sleep(1.5)
                logger.info("PNT focado: '%s' (pygetwindow)", w.title)
                return True

        logger.warning("Janela PNT não encontrada")
        return False
    except Exception as e:
        logger.warning("Erro ao focar PNT: %s", e)
        return False


def _obter_rect_pnt() -> tuple | None:
    """Obtém o retângulo da janela PNT: processo > HWND > pygetwindow."""
    hwnd = _achar_janela_pnt_por_processo()
    if not hwnd:
        hwnd = _achar_janela_pnt()
    if hwnd:
        try:
            import win32gui
            return win32gui.GetWindowRect(hwnd)
        except Exception:
            pass

    try:
        import pygetwindow as gw
        for pattern in _PNT_SEARCH_TITLES:
            windows = gw.getWindowsWithTitle(pattern)
            if windows:
                w = windows[0]
                return (w.left, w.top, w.left + w.width, w.top + w.height)
    except Exception:
        pass

    return None


def _minimizar_ide() -> None:
    """Minimiza o IDE (VS Code, Antigravity, Cursor, etc.) que atrapalha automação."""
    try:
        import pygetwindow as gw
        alvos = ["Visual Studio Code", "Antigravity", "Cursor", "Windsurf", "VSCodium"]
        for w in gw.getAllWindows():
            for alvo in alvos:
                if alvo.lower() in w.title.lower():
                    if not w.isMinimized:
                        w.minimize()
                        logger.info("IDE minimizado: '%s'", w.title)
                    return
    except Exception:
        pass


def _minimizar_outras_janelas(hwnd_pnt: int) -> None:
    """Minimiza todas as outras janelas visíveis para evitar sobreposição e falsos positivos."""
    try:
        import win32gui
        import win32con
        if not hwnd_pnt:
            return
        
        def enum_windows(hwnd, _):
            # Não minimiza o próprio PNT
            if hwnd != hwnd_pnt and win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                # Ignora a barra de tarefas do Windows, o Desktop e janelas de sistema essenciais
                if title and cls not in ["Shell_TrayWnd", "Progman", "WorkerW", "Windows.UI.Core.CoreWindow"]:
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return True
        
        win32gui.EnumWindows(enum_windows, None)
        time.sleep(0.5)
        logger.info("Outras janelas minimizadas para limpar a tela")
        print("[PNT]  Outras janelas minimizadas para limpar a tela")
    except Exception as e:
        logger.warning("Não foi possível minimizar outras janelas: %s", e)


def _debug_screenshot(images_dir: str, etapa: str) -> None:
    """Salva screenshot para debug no diretório de imagens."""
    try:
        path = Path(images_dir) / f"debug_{etapa}.png"
        pyautogui.screenshot(str(path))
        logger.info("Debug screenshot salvo: %s", path)
        print(f"[PNT] Debug screenshot salvo: {path}")
    except Exception as e:
        logger.warning("Erro ao salvar debug screenshot: %s", e)



def _diagnostic_list_windows() -> None:
    """Loga todas as janelas visíveis para debug quando PNT não é encontrado."""
    try:
        import win32gui
        visible = []
        def enum_all(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                if title:
                    visible.append(f"  HWND={hwnd} class='{cls}' title='{title}'")
            return True
        win32gui.EnumWindows(enum_all, None)
        logger.warning("Janelas visíveis encontradas:\n%s", "\n".join(visible[:30]))
    except Exception:
        pass


def executar_automacao_pnt(images_dir: str | None = None) -> bool:
    """
    Automatiza a importação de basket no PNT (FastTrader):
      1. Minimiza IDE/outras janelas
      2. Alt+F → Ferramentas; ↓ 4× + Enter → Importação de Basket/Ordens
      3. Tab + Alt+↓ + Home + ↓ 4× + Enter → "Robô - MultiLeg (ativo por coluna)"
      4. Tab + Ctrl+V → cola o basket

    Se *images_dir* for None, usa ``pnt_images/`` ao lado deste arquivo.
    Retorna True se OK, False caso contrário.
    """
    if images_dir is None:
        images_dir = str(Path(__file__).parent / "pnt_images")

    # --- 0. Localiza PNT (processo > título) e minimiza IDE/outros ------------
    hwnd_pnt = _achar_janela_pnt_por_processo()
    if not hwnd_pnt:
        logger.warning("Busca por processo falhou, tentando por título...")
        hwnd_pnt = _achar_janela_pnt()
    if not hwnd_pnt:
        print("[PNT] [ERRO] Janela do PNT não encontrada. Abra o FastTrader primeiro.")
        _diagnostic_list_windows()
        return False

    # Minimiza só o IDE (nunca outras janelas do usuário)
    _minimizar_ide()
    time.sleep(0.5)

    # --- 1. Forçar foco no PNT (tenta múltiplas vezes) ---------------------
    def _forcar_foco(hwnd):
        import win32gui
        import win32con
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)
            # SwitchToThisWindow (funciona de processo background)
            ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
            time.sleep(0.3)
            # Truque do Alt key: permite SetForegroundWindow de bg process
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
            time.sleep(0.1)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.3)
            rect = win32gui.GetWindowRect(hwnd)
            if rect:
                pyautogui.click((rect[0] + rect[2]) // 2, rect[1] + 15)
                time.sleep(0.3)
            return True
        except Exception as e:
            logger.warning("Foco falhou: %s", e)
            return False

    foco_ok = False
    for tentativa in range(3):
        if _forcar_foco(hwnd_pnt):
            import win32gui
            fg = win32gui.GetForegroundWindow()
            if fg == hwnd_pnt or win32gui.IsChild(hwnd_pnt, fg):
                foco_ok = True
                logger.info("PNT em foco (tentativa %d)", tentativa + 1)
                break
        logger.warning("Tentativa %d: PNT não está em foco, repetindo...", tentativa + 1)
        time.sleep(1.0)

    if not foco_ok:
        print("[PNT] [ERRO] Não foi possível trazer PNT para o primeiro plano.")
        return False

    # --- 2. Abrir menu Ferramentas (Alt+F) e navegar até Importação de Basket ---
    logger.info("Abrindo menu Ferramentas (Alt+F)...")
    pyautogui.hotkey("alt", "f")
    time.sleep(0.8)
    logger.info("Navegando para Importação de Basket/Ordens (↓4 + Enter)...")
    for _ in range(4):
        pyautogui.press("down")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(1.5)
    _debug_screenshot(images_dir, "apos_menu")

    # --- 3. Selecionar "Robô - MultiLeg" no dropdown via Win32 --------------
    logger.info("Procurando ComboBox 'Tipo de Ordem' no dialog de Importação...")
    try:
        combo = _achar_combobox(hwnd_pnt)
        if combo:
            hwnd_combo, rect = combo
            logger.info("ComboBox encontrado HWND=%s rect=%s", hwnd_combo, rect)
            ok = _selecionar_item_combobox(hwnd_combo, "Robô - MultiLeg (ativo por coluna)", rect)
            if ok:
                logger.info("Item 'Robô - MultiLeg' selecionado com sucesso!")
            else:
                logger.warning("Falha ao selecionar item via Win32, tentando teclado...")
                pyautogui.press("tab")
                time.sleep(0.2)
                pyautogui.hotkey("alt", "down")
                time.sleep(0.3)
                pyautogui.press("home")
                time.sleep(0.1)
                for _ in range(4):
                    pyautogui.press("down")
                    time.sleep(0.08)
                pyautogui.press("enter")
                time.sleep(0.3)
        else:
            logger.warning("ComboBox não encontrado, fallback teclado...")
            pyautogui.press("tab")
            time.sleep(0.2)
            pyautogui.hotkey("alt", "down")
            time.sleep(0.3)
            pyautogui.press("home")
            time.sleep(0.1)
            for _ in range(4):
                pyautogui.press("down")
                time.sleep(0.08)
            pyautogui.press("enter")
            time.sleep(0.3)

        # Tab + Ctrl+V
        pyautogui.press("tab")
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        logger.info("Basket colado com sucesso!")
        return True
    except Exception as e:
        logger.warning("Falha ao interagir com dropdown: %s", e)
        return False


class PNTIntegration:
    """Integração com PlugNTrade via automação de interface (GUI) usando Clipboard."""
    
    def __init__(self, db_path: str = None, progress_callback=None):
        self.db_path = db_path
        self.screen_manager = PNTScreenManager()
        self.progress_callback = progress_callback or (lambda pct, msg: None)
        
        pyautogui.PAUSE = 0.15
        pyautogui.FAILSAFE = True

    def _report(self, pct: int, msg: str):
        if self.progress_callback:
            self.progress_callback(pct, msg)
        logger.info("PNT [%d%%]: %s", pct, msg)

    def _get_param(self, chave: str):
        """Busca parâmetros operacionais no banco de dados."""
        try:
            from src.infrastructure.persistence.repositories.repositories import ParametroRepository
            from src.infrastructure.persistence.database import get_db_path
            repo = ParametroRepository(self.db_path or str(get_db_path()))
            p = repo.get_by_chave(chave)
            if p:
                return p.valor
        except Exception as e:
            logger.error(f"PNT: Erro ao buscar parâmetro {chave}: {e}")
        return None

    def _digitar_valor(self, valor):
        """Limpa o campo atual e digita o valor formatado (ponto para vírgula)."""
        if valor is None: return
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        valor_str = str(valor).replace('.', ',') if isinstance(valor, float) else str(valor)
        pyautogui.write(valor_str)
            
    def _preparar_dados_clipboard(self, opp, is_box, suffix):
        """Monta dados no formato de importação direcional do PlugNTrade."""
        linhas = []
        
        if is_box:
            lote_ativo = int(float(self._get_param(f'lote_ativo_{suffix}') or 0))
            linhas.append(f"{opp.ativo}\tC\t{lote_ativo}")
            
            lote_put = int(float(self._get_param(f'lote_put_{suffix}') or 0))
            linhas.append(f"{opp.cod_put}\tC\t{lote_put}")
            
            lote_call = int(float(self._get_param('lote_call_box') or 0))
            linhas.append(f"{opp.cod_call}\tC\t{lote_call}")
        else:
            lote_ativo = int(float(self._get_param(f'lote_ativo_{suffix}') or 0))
            linhas.append(f"{opp.ativo}\tC\t{lote_ativo}")
            
            lote_put = int(float(self._get_param(f'lote_put_{suffix}') or 0))
            linhas.append(f"{opp.cod_put}\tC\t{lote_put}")
            
        return "\n".join(linhas)

    def enviar_oportunidade(self, opp):
        """Envia a oportunidade usando o fluxo correto de importação do PNT."""
        if not opp: return

        self._report(10, "Buscando parâmetros da operação...")
        is_box = getattr(opp, 'operacao', '') in ("BOX", "BOXSBTH") or getattr(opp, 'is_box', False)
        suffix = "box" if is_box else "sbth"
        
        self._report(30, "Preparando dados formatados...")
        dados = self._preparar_dados_clipboard(opp, is_box, suffix)
        
        self._report(50, "Copiando para área de transferência...")
        pyperclip.copy(dados)
        
        self._report(70, "Localizando janela do PNT...")
        self.screen_manager.find_pnt_window()
        
        self._report(90, "Cole os dados no PNT (Ctrl+V)...")
        logger.info("PNT: Acesse manualmente:")
        logger.info("   Ferramentas > Importação de Ordens > Robô - Direcional")
        logger.info("PNT: Posicione o cursor no campo e pressione Ctrl+V")
        time.sleep(1)
        
        self._report(100, "Dados enviados para o PNT!")