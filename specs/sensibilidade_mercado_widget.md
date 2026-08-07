# SensibilidadeMercadoWidget

Widget de análise de sensibilidade de mercado em tempo real. Exibe: (1) cards de Dólar (WIN/WDO), Juros (DI1F33 + curva), Commodities (BRENT/EWZS) e Vetor (RISK-ON/OFF/etc.), (2) grid de ativos IBOV com ADRs, (3) termômetro de pressão de mercado, (4) rosa dos ventos decorativa como marca d'água.

Integra-se com OpenFast para cotações BR e com `yfinance` (via `_AdrFetcher` QThread) para ADRs. Usa `MarketAnalyzer` para classificação de vetor e curva de DI.

## Contrato (Requisitos)

### `SensibilidadeMercadoWidget(db_path=None, source=None, parent=None) -> None`
**Garante:**
1. Timer de refresh a cada 3s.
2. Inicia `_AdrFetcher` QThread para polling de ADRs a cada 60s.
3. Monta grid com futuros (WIN, WDO, DI1F27, DI1F33, BRENT, EWZS) + composição IBOV (top 50% peso).
4. Exibe status de conexão (bolinha verde = conectado, laranja = desconectado).

### `_atualizar() -> None`
**Garante:**
1. Atualiza CDI (cache 300s), preços, e análise de mercado.
2. Atualiza labels do grid e barra IBOV.

### `_atualizar_precos() -> None`
**Garante:**
1. Lê `LAST_PRICE` (fallback: BID → ASK) do source para cada código.
2. Calcula variação: `VARIATION` oficial → `(LAST - CLOSE)/CLOSE` → referência intraday.
3. Para ativos com alternativas (PETR4→PETR3, BBDC4→BBDC3), também busca preço da alternativa.

### `_atualizar_analise() -> None`
**Garante:**
1. Extrai variações de WIN, WDO, DI1F33 (pontos), BRENT, EWZS.
2. Chama `MarketAnalyzer.analisar_curva_di(di1f33_pontos)` para classificação da curva de juros.
3. Chama `MarketAnalyzer.analisar_vetor(...)` para classificação RISK-ON/OFF/COMMODITIES/DEFENSIVO/MISTO.
4. Atualiza cores de borda dos cards conforme direção dos indicadores.
5. Atualiza termômetro com blocos coloridos e descrição textual.

## Classes Auxiliares

### `_AdrFetcher(QThread)`
**Garante:**
1. Polling a cada 60s de ADRs via `yfinance.Tickers`.
2. Até 2 retentativas com sleep 2s entre falhas.
3. Emite `dados_atualizados` Signal com dict `{ticker: {preco, anterior, var_pct, ts}}`.
4. Cache thread-safe com `threading.Lock`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `logging` | — | Logs de debug e erro |
| `math` | — | Cálculo de CDI mensal e ângulos da rosa dos ventos |
| `threading` | `Lock` | Thread safety no `_AdrFetcher` |
| `time` | — | Cache CDI e timestamps ADR |
| `datetime` | `date`, `timedelta` | Datas de vencimento e referência |
| `typing` | `Any` | Type hints |
| `numpy` | `np` | Cálculo de dias úteis (`busday_count`) |
| `PySide6.QtCore` | `QPointF`, `Qt`, `QThread`, `QTimer`, `Signal` | UI thread e sinais |
| `PySide6.QtGui` | `QBrush`, `QColor`, `QFont`, `QPainter`, `QPen`, `QPixmap` | Renderização |
| `PySide6.QtWidgets` | Vários | Layout e widgets |
| `src.domain.services.analise_mercado` | `MarketAnalyzer` | Classificação de vetor e curva |
| `src.domain.services.calendario_b3` | `B3_CALENDAR` | Calendar de dias úteis para vencimentos |
| `src.domain.services.market_data_source` | `FieldName` | Enum de campos RTD |
| `src.infrastructure.integrations.ibov_composition_client` | `IbovCompositionClient` | Composição do IBOV |
| `src.infrastructure.persistence.database` | `get_db_path` | Fallback db_path |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Leitura da taxa CDI |
| `yfinance` | `yf` | ADR prices (import lazy em `_AdrFetcher`) |

## Métricas

| Linhas | 957 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-08-03
- O `ADR_MAP` mapeia tickers BR para ADRs. Inclui mapeamentos alternativos (PETR3→PBR, BBDC3→BBD). PETR3 e BBDC3 são pulados no grid (só PETR4 e BBDC4 são exibidos), mas suas alternativas são assinadas para fallback de preço.
- A rosa dos ventos é puramente decorativa — renderizada como marca d'água semi-transparente (opacidade 0.35) no `paintEvent`.
- O cálculo de vencimento WIN usa "quarta-feira mais próxima do dia 15", WDO usa "primeiro dia útil do mês".
- `_limpar_nome_ativo` tem workarounds para nomes que vêm truncados ("DI1 Jan/2" → "DI1F27").
- `_on_adr_atualizado` é um no-op (`pass`) — os dados ADR são lidos sob demanda em `_update_adr_in_row` via `_adr_fetcher.obter()`.
