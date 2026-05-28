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

PYNT_TITLES = ["PnT", "PlugNTrade", "FastTrader", "PnT_FastTrader", "Profit"]

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
                win32gui.SetForegroundWindow(hwnd)
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
        """Abre a tela Multileg manualmente (usuário deve fazer isso)"""
        logger.info("Por favor, abra manualmente a tela Multileg no PNT...")
        time.sleep(2)
        return self.find_pnt_window()
    
    def open_spread_screen(self):
        """Abre a tela Spread manualmente (usuário deve fazer isso)"""
        logger.info("Por favor, abra manualmente a tela Spread no PNT...")
        time.sleep(2)
        return self.find_pnt_window()

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