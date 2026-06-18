"""Testes unitários da automação PNT com mocks (mercado fechado)."""
import sys
from unittest.mock import patch, MagicMock
import pytest

# ── Correção 1: import ctypes ──────────────────────────────────────────────
def test_ctypes_importado():
    import ctypes
    assert hasattr(ctypes, "windll")


# ── Correção 2: SwitchToThisWindow ─────────────────────────────────────────
class TestSwitchToThisWindow:

    def test_switchtothiswindow_usado(self):
        p_has = patch("src.infrastructure.integrations.pnt.HAS_WIN32", True)
        mock_ctypes = MagicMock()
        p_ctypes = patch("src.infrastructure.integrations.pnt.ctypes", mock_ctypes)
        p_time = patch("src.infrastructure.integrations.pnt.time")
        p_por_processo = patch(
            "src.infrastructure.integrations.pnt._achar_janela_pnt_por_processo",
            return_value=None,
        )
        p_achar = patch(
            "src.infrastructure.integrations.pnt._achar_janela_pnt",
            return_value=12345,
        )
        p_has.start()
        p_ctypes.start()
        p_time.start()
        p_por_processo.start()
        p_achar.start()

        try:
            from src.infrastructure.integrations.pnt import _focar_janela_pnt

            result = _focar_janela_pnt()

            assert result is True
            mock_ctypes.windll.user32.SwitchToThisWindow.assert_called_once_with(
                12345, True
            )
        finally:
            for p in (p_has, p_ctypes, p_time, p_por_processo, p_achar):
                p.stop()

    def test_screen_manager_usa_switchtothiswindow(self):
        mock_ctypes = MagicMock()
        p_ctypes = patch("src.infrastructure.integrations.pnt.ctypes", mock_ctypes)

        mock_w32 = MagicMock()
        mock_w32.IsWindowVisible.return_value = True
        mock_w32.GetWindowText.return_value = "FastTrader"
        mock_w32.IsIconic.return_value = False
        mock_w32.EnumWindows = lambda cb, _: cb(99999, None) or True
        p_w32 = patch("src.infrastructure.integrations.pnt.win32gui", mock_w32)

        p_has = patch("src.infrastructure.integrations.pnt.HAS_WIN32", True)
        p_con = patch("src.infrastructure.integrations.pnt.win32con")
        p_time = patch("src.infrastructure.integrations.pnt.time")

        p_has.start()
        p_ctypes.start()
        p_w32.start()
        p_con.start()
        p_time.start()

        try:
            from src.infrastructure.integrations.pnt import PNTScreenManager

            sm = PNTScreenManager()

            result = sm._find_pnt_window_win32()

            assert result is True
            mock_ctypes.windll.user32.SwitchToThisWindow.assert_called_once_with(
                99999, True
            )
        finally:
            for p in (p_has, p_ctypes, p_w32, p_con, p_time):
                p.stop()


# ── Correção 3: Robô com acento ────────────────────────────────────────────
class TestRoboComAcento:

    def test_funcao_exporta_robo_com_acento(self):
        from src.infrastructure.integrations.pnt import executar_automacao_pnt
        assert executar_automacao_pnt is not None

    def test_pyautogui_altdown_home_down_enter(self):
        mock_pyauto = MagicMock()

        patches = [
            patch("src.infrastructure.integrations.pnt.pyautogui", mock_pyauto),
            patch("src.infrastructure.integrations.pnt._focar_janela_pnt",
                  return_value=True),
            patch("src.infrastructure.integrations.pnt._obter_rect_pnt",
                  return_value=(0, 0, 800, 600)),
            patch("src.infrastructure.integrations.pnt._minimizar_ide"),
            patch("src.infrastructure.integrations.pnt._debug_screenshot"),
            patch("src.infrastructure.integrations.pnt._achar_combobox",
                  return_value=None),
            patch("src.infrastructure.integrations.pnt.time"),
        ]

        for p in patches:
            p.start()

        try:
            from src.infrastructure.integrations.pnt import executar_automacao_pnt

            result = executar_automacao_pnt(images_dir=".")

            assert result is True

            # Verifica Alt+Down (abre dropdown read-only)
            chamadas_hotkey = mock_pyauto.hotkey.call_args_list
            assert any(
                args == ("alt", "down")
                for args, _ in chamadas_hotkey
            ), "Alt+Down deve ser chamado para abrir o dropdown"

            # Verifica Home + 4×Down + Enter (navega até item 5)
            chamadas_press = mock_pyauto.press.call_args_list
            args_flat = [a[0] for a, _ in chamadas_press]
            assert "home" in args_flat, "Home deve ser pressionado"
            assert args_flat.count("down") >= 4, "Down deve ser pressionado 4x"
            assert "enter" in args_flat, "Enter deve ser pressionado"

            # Verifica Ctrl+V final
            assert any(
                args == ("ctrl", "v")
                for args, _ in chamadas_hotkey
            ), "Ctrl+V deve ser chamado para colar o basket"
        finally:
            for p in patches:
                p.stop()


class TestBuscaPorProcesso:
    def test_achar_por_processo_encontra_pnt(self):
        import sys
        mock_psutil = MagicMock()
        mock_proc = MagicMock()
        mock_proc.info = {'pid': 1234, 'name': 'PnT.Inteface.exe'}
        mock_psutil.process_iter.return_value = [mock_proc]

        patches = [
            patch.dict("sys.modules", {"psutil": mock_psutil}),
            patch("win32gui.IsWindowVisible", return_value=True),
            patch("win32gui.EnumWindows", side_effect=lambda cb, _: cb(99999, None) or True),
            patch("win32process.GetWindowThreadProcessId", return_value=(None, 1234)),
            patch("win32gui.GetWindowRect", return_value=(0, 0, 100, 100)),
        ]
        for p in patches:
            p.start()
        try:
            from src.infrastructure.integrations.pnt import _achar_janela_pnt_por_processo
            hwnd = _achar_janela_pnt_por_processo()
            assert hwnd == 99999
        finally:
            for p in patches:
                p.stop()
