# Correção PNT — Busca por Processo

## Problema
`_focar_janela_pnt()` buscava por título de janela. O padrão "PnT" (3 letras) casava com o título do VS Code quando `pnt.py` estava aberto ("pnt.py - Spreadhunter - Visual Studio Code"), fazendo o PyAutoGUI clicar dentro do VS Code em vez do PNT.

## Solução
Substituir busca por título por busca pelo nome do processo (`PnT.Inteface.exe`).

## Arquivo
`src/infrastructure/integrations/pnt.py`

### 1. Remover "PnT" e "Profit" das listas (linhas 20, 103-112, 114-123)

Original `PYNT_TITLES` (linha 20):
```python
PYNT_TITLES = ["PnT", "PlugNTrade", "PlugAndTrade", "Plug & Trade", "FastTrader", "PnT_FastTrader", "Profit"]
```
Nova:
```python
PYNT_TITLES = ["PlugNTrade", "PlugAndTrade", "Plug & Trade", "FastTrader", "PnT_FastTrader"]
```

Original `_PNT_WINDOW_TITLES` (linha 103-112):
```python
_PNT_WINDOW_TITLES = [
    "FastTrader - Plug and Trade",
    "FastTrader",
    "PnT",
    "PlugNTrade",
    "PlugAndTrade",
    "Plug & Trade",
    "PnT_FastTrader",
    "Profit",
]
```
Nova:
```python
_PNT_WINDOW_TITLES = [
    "FastTrader - Plug and Trade",
    "FastTrader",
    "PlugNTrade",
    "PlugAndTrade",
    "Plug & Trade",
    "PnT_FastTrader",
]
```

Original `_PNT_SEARCH_TITLES` (linha 114-123):
```python
_PNT_SEARCH_TITLES = [
    "Plug and Trade",
    "FastTrader",
    "PnT",
    "PlugNTrade",
    "PlugAndTrade",
    "Plug & Trade",
    "PnT_FastTrader",
    "Profit",
]
```
Nova:
```python
_PNT_SEARCH_TITLES = [
    "Plug and Trade",
    "FastTrader",
    "PlugNTrade",
    "PlugAndTrade",
    "Plug & Trade",
    "PnT_FastTrader",
]
```

### 2. Adicionar `_achar_janela_pnt_por_processo()` (após `_achar_janela_pnt()`, linha 160)

Inserir após o `except` da linha 159-160:

```python
def _achar_janela_pnt_por_processo() -> int | None:
    """Localiza HWND do PNT pelo nome do processo PnT.Inteface.exe."""
    try:
        import psutil
        import win32gui
        import win32process

        pids = set()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if (proc.info['name'] or '').lower() == 'pnt.inteface.exe':
                    pids.add(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if not pids:
            return None

        found = [0]
        def enum_windows(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid in pids:
                found[0] = hwnd
                return False
            return True

        win32gui.EnumWindows(enum_windows, None)
        return found[0] or None
    except Exception:
        return None
```

### 3. Modificar `_focar_janela_pnt()` (linhas 284-320)

Substituir por:

```python
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
            rect = win32gui.GetWindowRect(hwnd)
            if rect:
                pyautogui.click((rect[0] + rect[2]) // 2, rect[1] + 15)
                time.sleep(1.0)
                logger.info("PNT focado por processo (click na barra de título)!")
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
```

### 4. Modificar `_obter_rect_pnt()` (linhas 323-343)

Substituir por:

```python
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
```

## Arquivo de teste
`tests/infrastructure/test_pnt.py`

### Atualizar teste `test_switchtothiswindow_usado`

Mudar o mock para `_achar_janela_pnt_por_processo` retornar None (para cair no fallback título):

```python
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
```

### Adicionar teste para busca por processo

```python
class TestBuscaPorProcesso:
    def test_achar_por_processo_encontra_pnt(self):
        mock_psutil = MagicMock()
        mock_proc = MagicMock()
        mock_proc.info = {'pid': 1234, 'name': 'PnT.Inteface.exe'}
        mock_psutil.process_iter.return_value = [mock_proc]

        mock_w32 = MagicMock()
        mock_w32.IsWindowVisible.return_value = True
        mock_w32.GetWindowRect.return_value = (0, 0, 800, 600)
        mock_w32.EnumWindows = lambda cb, _: cb(99999, None) or True

        mock_process = MagicMock()
        mock_process.GetWindowThreadProcessId.return_value = (None, 1234)

        patches = [
            patch("src.infrastructure.integrations.pnt.psutil", mock_psutil),
            patch("src.infrastructure.integrations.pnt.win32gui", mock_w32),
            patch("src.infrastructure.integrations.pnt.win32process", mock_process),
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
```
