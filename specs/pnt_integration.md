# PNTIntegration

Integração com o PlugNTrade (FastTrader) via automação de interface gráfica (GUI automation). Usa `pyautogui`, `win32gui` e `pyperclip` para automatizar a importação de baskets de opções no PNT: localiza a janela, navega menus, seleciona dropdown e cola dados da clipboard.

## Contrato (Requisitos)

### `PNTScreenManager.__init__()`
**Garante:**
1. Cria diretório `scratch/pnt_screens` para debug screenshots.

### `PNTScreenManager.find_pnt_window() -> bool`
**Garante:**
1. Tenta Win32 API primeiro (`_find_pnt_window_win32`): enumera janelas visíveis, procura por títulos contendo "PlugNTrade", "PlugAndTrade", "Plug & Trade", "FastTrader", "PnT_FastTrader".
2. Se encontrada, restaura se minimizada, foca via `SwitchToThisWindow` e aguarda 1s.
3. Fallback: `_find_pnt_window_pyautogui` via `pyautogui.getWindowsWithTitle`.

### `executar_automacao_pnt(images_dir=None) -> bool`
**Garante:**
1. Localiza janela PNT por processo (`pnt.interface.exe`) ou título.
2. Minimiza IDE (VS Code, Cursor, etc.) para evitar sobreposição.
3. Força foco na janela PNT (até 3 tentativas com `SwitchToThisWindow`, `keybd_event` Alt, `SetForegroundWindow`, clique).
4. Abre menu Ferramentas (Alt+F), navega ↓4 + Enter para "Importação de Basket/Ordens".
5. Localiza ComboBox "Tipo de Ordem" via Win32 API (`_achar_combobox`).
6. Seleciona "Robô - MultiLeg (ativo por coluna)" no dropdown.
7. Tab + Ctrl+V para colar o basket.

### `_achar_combobox(hwnd_pai) -> tuple | None`
**Garante:**
1. Localiza o dialog "Importação de Basket" como janela filha ou standalone.
2. Enumera `ComboBox` children visíveis, seleciona o com menor `y` (mais ao topo = "Tipo de Ordem").
3. Retorna `(hwnd_combo, rect)`.

### `_selecionar_item_combobox(hwnd_combo, texto, rect) -> bool`
**Garante:**
1. Usa `CB_FINDSTRINGEXACT` para obter índice do item alvo.
2. Clica na seta direita do dropdown para abrir a lista.
3. Navega com Home + Down×N até o índice alvo e pressiona Enter.
4. Fallback (se `CB_FINDSTRINGEXACT` falhar cross-process): digita o texto para autocomplete.
5. Verifica seleção via `CB_GETCURSEL`.

### `PNTIntegration.__init__(db_path=None, progress_callback=None)`
**Garante:**
1. Instancia `PNTScreenManager`.
2. Configura `pyautogui.PAUSE = 0.15` e `FAILSAFE = True`.

### `PNTIntegration.enviar_oportunidade(opp)`
**Garante:**
1. Detecta se é Box ou SBTH via `opp.operacao`.
2. Busca parâmetros de lote do banco (`lote_ativo_box`, `lote_put_box`, etc.).
3. Monta dados formatados (ticker + lado + quantidade, separados por tab).
4. Copia para clipboard via `pyperclip.copy`.
5. Localiza e foca janela PNT.
6. Instrui usuário a colar manualmente (Ctrl+V) no campo correto.

### `_achar_janela_pnt_por_processo() -> int | None`
**Garante:**
1. Usa `psutil` para encontrar processos `pnt.interface.exe` ou `fasttrader.exe`.
2. Enumera janelas visíveis desses processos, seleciona a maior por área.
3. Mais confiável que busca por título (não depende do texto da janela).

### `_focar_janela_pnt() -> bool`
**Garante:**
1. Tenta foco por processo → título Win32 → pygetwindow (3 níveis de fallback).

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `ctypes` | `ctypes` | `windll.user32.SwitchToThisWindow` |
| `pyautogui` | `pyautogui` | Automação de mouse/teclado |
| `pyperclip` | `pyperclip` | Clipboard |
| `time` | `time` | Sleeps entre ações |
| `logging` | `logging` | Logger |
| `pathlib` | `Path` | Paths de arquivos |
| `win32gui` (runtime) | - | Win32 API para janelas |
| `win32con` (runtime) | - | Constantes Win32 |
| `win32process` (runtime) | - | `GetWindowThreadProcessId` |
| `psutil` (runtime) | - | Listagem de processos |
| `pygetwindow` (runtime) | - | Fallback para automação de janelas |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 706 |
| Última modificação | 2026-06-18 |
| Classes | 2 (`PNTScreenManager`, `PNTIntegration`) |

## Notas

- 2026-06-18 — última modificação.
- Altamente dependente de UI — qualquer mudança no layout do PNT (posição de menus, títulos de janela, ordem de dropdowns) quebra a automação.
- `CB_FINDSTRINGEXACT` pode falhar cross-process (Windows bloqueia mensagens entre processos de integridade diferente). O fallback por digitação mitiga isso.
- `_minimizar_ide` minimiza VS Code e similares para evitar que sobreponham o PNT durante screenshots de debug.
- A automação NÃO fecha o dialog de importação nem confirma a operação — apenas cola os dados. O usuário precisa confirmar manualmente.
- `enviar_oportunidade` apenas copia para clipboard e instrui o usuário — não executa a automação completa como `executar_automacao_pnt`.
