# Prompt para Gemini — Diagnóstico da automação PNT

## Contexto
Estou automatizando a importação de baskets no PNT (FastTrader) via PyAutoGUI + win32 API. O script encontra o ComboBox da tela de importação, programa a seleção do item "Robô - MultiLeg (ativo por coluna)" usando mensagens `CB_FINDSTRINGEXACT` + `CB_SETCURSEL` + `CBN_SELCHANGE`, e depois dá Ctrl+V.

## Problema
O script roda sem erros, o dropdown fica com valor correto programaticamente, mas o PNT não reage como se tivesse sido alterado — parece que o robô do PNT não registra a mudança.

## Código da função de seleção

```python
def _selecionar_item_combobox(hwnd_combo: int, texto: str) -> bool:
    try:
        import win32gui
        import win32con
        index = win32gui.SendMessage(hwnd_combo, win32con.CB_FINDSTRINGEXACT, -1, texto)
        if index == win32con.CB_ERR:
            return False
        win32gui.SendMessage(hwnd_combo, win32con.CB_SETCURSEL, index, 0)
        # Notifica o pai
        parent = win32gui.GetParent(hwnd_combo)
        ctrl_id = win32gui.GetDlgCtrlID(hwnd_combo)
        win32gui.SendMessage(parent, win32con.WM_COMMAND,
            win32con.CBN_SELCHANGE << 16 | ctrl_id, hwnd_combo)
        return True
    except Exception as e:
        return False
```

## Perguntas
1. O `CB_SETCURSEL` seguido de `CBN_SELCHANGE` é suficiente para um ComboBox do PNT reconhecer a mudança?
2. Existe outra notificação necessária? (`CBN_SELENDOK`? `CBN_CLOSEUP`?)
3. O PNT pode estar usando um controle customizado que não responde a `CB_FINDSTRINGEXACT`?

## Anexos
(coloque aqui os prints: debug_apos_menu.png e debug_dropdown_nao_achado.png, se houver)
