import pyautogui
import pyperclip
import time
import logging
from pathlib import Path

try:
    from src.application.dtos.dtos import OportunidadeMonitor
except ImportError:
    OportunidadeMonitor = None

logger = logging.getLogger(__name__)

class PNTScreenManager:
    """Gerenciador de telas do PNT via reconhecimento de imagem"""
    
    def __init__(self):
        self.screens_dir = Path("scratch/pnt_screens")
        self.screens_dir.mkdir(exist_ok=True)
        
    def find_pnt_window(self):
        """Encontra e foca a janela do PNT"""
        try:
            titles = ["PnT", "PlugNTrade", "FastTrader", "PnT_FastTrader", "Profit"]
            win = None
            for t in titles:
                wins = pyautogui.getWindowsWithTitle(t)
                if wins:
                    win = wins[0]
                    break
            
            if win:
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(1.0)
                logger.info("PNT focado com sucesso!")
                return True
            else:
                logger.warning("Nenhuma janela do PNT encontrada")
                return False
        except Exception as e:
            logger.warning(f"Erro ao focar PNT: {e}")
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
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self.screen_manager = PNTScreenManager()
        
        pyautogui.PAUSE = 0.15
        pyautogui.FAILSAFE = True

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

        self.screen_manager.find_pnt_window()
        is_box = getattr(opp, 'operacao', '') in ("BOX", "BOXSBTH") or getattr(opp, 'is_box', False)
        suffix = "box" if is_box else "sbth"
        
        logger.info("PNT: Iniciando integração...")
        
        # 1. Preparar dados no formato correto (tab separado)
        dados = self._preparar_dados_clipboard(opp, is_box, suffix)
        pyperclip.copy(dados)
        logger.info(f"PNT: Dados copiados ({len(dados.split(chr(10)))} linha(s))")
        
        # 2. Acessar a tela de importação (manualmente)
        logger.info("PNT: Acesse manualmente:")
        logger.info("   Ferramentas > Importação de Ordens > Robô - Direcional")
        logger.info("PNT: Posicione o cursor no campo e pressione Ctrl+V")
        time.sleep(1)
        
        logger.info("PNT: Dados enviados! Se aparecer 'Configurar e Executar…' no PNT, está OK.")