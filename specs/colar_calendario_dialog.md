# ColarCalendarioDialog

## Propósito

Diálogo de monitoramento de Collar Calendário — a estratégia mais complexa do sistema. Exibe tabela com resultados de collar calendário (base + otimizados), filtros avançados (delta/theta/CDI), visualização de zonas de probabilidade com `ZonaBarWidget`, score de qualidade com estrelas, resumo analítico (`_ResumoAnaliticoDialog`), e integração com proteção de cauda (BWB, tail protect). ~2870 linhas — o maior arquivo de UI do projeto.

## Contrato (Requisitos)

### `_setup_ui()`
**Garante:**
1. Painel esquerdo com filtros complexos: ativo (texto + checklist), delta min/max, theta min, CDI min, dias min/max, Top-N, variante.
2. Tabela com `ColarCalendarioTableModel` + `ColarCalendarioSortProxy`.
3. Coluna "Qualidade" com delegate customizado que renderiza barra de zonas + estrelas.
4. Botão sino, exportação CSV, status label.

### `_calcular_qualidade(r) -> int`
**Garante:**
1. Score 0-100 baseado em: PnL projetado (25pts se >0), CDI (25pts se >=2.5, 15pts se >=1.5), score EV ou score tradicional, probabilidade da zona C.
2. Para otimizados: usa `score_ev_pct` e `zona_c_prob`; para base: usa `score` e `risco_pct`.
3. Retorna `min(pontos, 100)`.

### `ZonaBarWidget`
**Garante:**
1. Barra horizontal pintada com 4 cores representando as zonas de probabilidade: vermelho (cauda esquerda), laranja (ganho parcial), verde (lucro máximo), azul (cap direito).
2. Largura proporcional às probabilidades fornecidas.

### `_ResumoAnaliticoDialog`
**Garante:**
1. Cards estilizados (background `#1a1a2e`) para: Qualidade & Decisão, Estrutura, Proteção de Cauda, Métricas de Risco, Irmãos (variantes do mesmo chassi).
2. Exibe estrelas (★), score EV, theta, zonas de probabilidade, PnL, CDI, IV Rank, Delta, Gamma, Vega.
3. Botões: Payoff, Gráfico Histórico, Basket PNT, Exportar Debug.

### Proteção de cauda (BWB/Tail)
**Garante:**
1. `_parse_zonas_json(json_str)`: extrai probabilidades e EVs do JSON de zonas.
2. `_extrair_zona_c_prob(r)`: extrai probabilidade da zona C (lucro máximo).
3. Integração com `CalculadoraProtecaoCauda` para exibir dados de BWB (Butterfly) e tail protect.

### `restaurar_selecao(ativos: list[str])`
**Garante:**
1. Marca checkboxes conforme lista e aplica filtro.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `json` | stdlib | Parse de zonas EV |
| `logging` | stdlib | Logging |
| `PySide6.QtWidgets` | `QDialog, QVBoxLayout, ..., QSizePolicy` | UI framework |
| `PySide6.QtCore` | `Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, Signal, QRect` | Modelo e sinais |
| `PySide6.QtGui` | `QFont, QColor, QBrush, QPainter, QPen` | Renderização |
| `src.domain.services.calendario_b3` | `dc_to_du` | Dias úteis |
| `src.infrastructure.integrations.opcoesnet_client` | `OpcoesNetClient` | Histórico |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Parâmetros |
| `src.ui.desktop.column_utils` | `salvar_ordem_colunas, salvar_largura_colunas, limpar_e_restaurar_colunas` | Persistência |
| `src.ui.desktop.copy_utils` | `copiar_texto_formatado, copiar_figura_clipboard, salvar_figura_arquivo` | Exportação |
| `src.ui.desktop.theme` | `Palette` | Cores |
| `src.ui.desktop.constants` | `SELETOR_TODOS` | Constante |

## Métricas

| Linhas | 2871 |
| Classes | 5+ (`ColarCalendarioTableModel`, `ColarCalendarioSortProxy`, `ColarCalendarioDialog`, `ZonaBarWidget`, `_ResumoAnaliticoDialog`, `_QualidadeDelegate`) |
| Testes | Não (testado indiretamente via integração) |

## Notas

- **Arquivo mais longo de UI (2871 linhas):** Alto acoplamento — modelo, proxy, delegate, widgets customizados e diálogo principal no mesmo arquivo. Refatoração recomendada: separar `ZonaBarWidget`, delegate e `_ResumoAnaliticoDialog` em arquivos próprios.
- **`_calcular_qualidade` e `_estrelas_str`:** Funções de nível módulo (não métodos) — usadas tanto pelo diálogo principal quanto pelo `_ResumoAnaliticoDialog`.
- **`_ResumoAnaliticoDialog` como classe interna:** Definido dentro do mesmo arquivo, acessa `r` (resultado) e `_irmaos` (variantes do mesmo chassi) para mostrar comparação entre estágios.
- **Proteção de cauda complexa:** O diálogo renderiza dados de BWB (butterfly spreads para proteção de cauda) e tail protect — features que só existem no contexto de collar calendário otimizado.
- **Zonas EV em JSON:** `zonas_ev_json` é um campo JSON com 4 probabilidades + 4 EVs, parseado via `json.loads` em tempo de renderização.
