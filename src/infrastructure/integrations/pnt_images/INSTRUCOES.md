# Automação Basket PNT — instruções de uso

## Visão Geral

A função `executar_automacao_pnt()` automatiza a importação de baskets
no PNT (FastTrader) via PyAutoGUI. Ela:

1. Foca a janela do PNT
2. Clica no menu **Ferramentas**
3. Navega (↓ 4× + Enter) para abrir "Importação de Ordens"
4. Clica no dropdown **Tipo de Ordem**
5. Localiza o texto **"Robô - MultiLeg (ativo por coluna)"** na lista e clica
6. Cola o clipboard com **Ctrl+V**

## Imagens necessárias

Salvar em `pnt_images/`:

| Arquivo | Conteúdo |
|---------|----------|
| `ferramentas.png` | Menu **Ferramentas** na barra do PNT |
| `robodirecional.png` | Dropdown (qualquer valor) |
| `tipo_ordem.png` | Texto **"Robô - MultiLeg (ativo por coluna)"** na lista suspensa |

Capturar com Recorte do Windows (Win+Shift+S) — apenas a região do
elemento, sem sobras.

## Como testar

```python
from src.infrastructure.integrations.pnt import executar_automacao_pnt
executar_automacao_pnt()
```

## Integrar no clique do "📋 Basket PNT"

Em `src/ui/desktop/boleta_dialog.py`, no final do método `_copiar()`:

```python
from src.infrastructure.integrations.pnt import executar_automacao_pnt
executar_automacao_pnt()
```

Assim, ao clicar "📋 Copiar Basket PNT", o sistema copia os dados e já dispara a automação.

## Fluxo

```
Usuário clica "📋 Basket PNT" (em Box/Colar/Colar Calendário)
  → BoletaDialog abre com as pernas do basket
    → Usuário clica "📋 Copiar Basket PNT"
      → Dados vão pro clipboard
      → executar_automacao_pnt() dispara:
        1. Foca FastTrader
        2. Menu Ferramentas → ↓ 4× → Enter
        3. Seleciona "Robô - MultiLeg (ativo por coluna)"
        4. Ctrl+V
      → Basket colado no PNT ✅
```

## Dependências

Instaladas via pip:
- `pyautogui` (automação de tela)
- `pygetwindow` (localizar janela)
- `opencv-python` (reconhecimento de imagem com `confidence`)

Adicionadas ao `pyproject.toml`.
