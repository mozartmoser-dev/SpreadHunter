# theme

Sistema de temas visuais do SpreadHunter. Define a folha de estilo QSS base (`DARK_THEME_QSS`), a paleta de cores semânticas (`Palette`) e o mecanismo de substituição de cores para temas alternativos (`THEME_REPLACEMENTS` + `get_theme_qss()`).

Três temas disponíveis: Azul Marinho (0.0, default), Grafite/Slate Gray (1.0), True Dark/Charcoal (2.0).

## Contrato (Requisitos)

### `Palette` (classe)
**Garante:**
1. Constantes de cor para uso programático em todo o sistema.
2. Categorias: Background (`BG_DARK`, `BG_BASE`, `BG_RAISED`, `BG_SURFACE`, `BG_HOVER`, `TABLE_BG`), Texto (`TEXT_PRIMARY`, `TEXT_SECONDARY`, `TEXT_MUTED`), Acento (`ACCENT_BLUE`, `ACCENT_BLUE_BRIGHT`), Status (`GREEN`, `RED`, `ORANGE`, `YELLOW`, `CYAN`, `PURPLE`), Linhas de tabela (`ROW_BOX`, `ROW_SBTH`, `ROW_BOXSBTH`, `ROW_NOT_VIABLE`, `ROW_LEILAO`), Liquidez (`LIQ_POSITIVE`, `LIQ_NEGATIVE`), e `STRIKEOUT_COLOR`.

### `get_theme_qss(theme_id) -> str`
**Garante:**
1. Aplica substituições de `THEME_REPLACEMENTS[theme_id]` sobre `DARK_THEME_QSS`.
2. Cada substituição é aplicada tanto em lowercase quanto uppercase da cor original.
3. Se `theme_id` não está no dict, retorna QSS sem alterações.

### `DARK_THEME_QSS` (string)
**Garante:**
1. Folha de estilo completa cobrindo: Global, Buttons (incluindo classes `primary`, `danger`, `success`, `monitor-active`), Toolbar, StatusBar, TableView, GroupBox, FormLayout, LineEdit, ComboBox, SpinBox, ProgressBar, ScrollArea, ScrollBar, MessageBox, TabWidget, ToolTip, Menu.
2. Fonte monospace para tabelas (`JetBrains Mono`, `Consolas`, `Courier New`).
3. Cores base Azul Marinho (#1a1a2e, #16213e, #0f0f23).

## Dependências Diretas (por import)

Nenhuma — módulo puramente declarativo, sem imports.

## Métricas

| Linhas | 520 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-08-06
- `THEME_REPLACEMENTS` usa chaves `float` (0.0, 1.0, 2.0) — isso combina com o parâmetro `tema_visual` que é armazenado como float no banco.
- A substituição de cores é feita com `str.replace()` simples, o que significa que cores que são substrings de outras cores (ex: `#1a1a2e` vs `#1a1a2e0`) podem gerar substituições incorretas. Na prática, as cores do tema são suficientemente distintas para evitar esse problema.
- O tema Grafite mapeia `#2d4a7a` → `#3b82f6` (azul Tailwind), o que torna o destaque de seleção em tabelas mais vibrante.
- A classe `Palette` tem atributos de classe que são strings — não há encapsulamento, são acessados diretamente como `Palette.BG_BASE`.
- `ROW_BOX`, `ROW_SBTH`, `ROW_BOXSBTH`, `ROW_NOT_VIABLE`, `ROW_LEILAO` são cores de fundo de linha usadas nos modelos de tabela para colorir linhas por tipo de operação.
