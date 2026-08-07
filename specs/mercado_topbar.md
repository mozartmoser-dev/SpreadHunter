# MercadoTopBarWidget

Barra superior compacta que exibe cotações em tempo real de CDI, futuros B3 (WIN, WDO, DI1), IBOV, VIX e um ticker de eventos corporativos (balanços e proventos). Implementa um letreiro digital com rolagem contínua (`TickerWidget`) e painel expansível com ações BR, futuros e ADRs.

Duplo-clique expande/recolhe o painel detalhado (ações BR, futuros e ADRs).

## Contrato (Requisitos)

### `MercadoTopBarWidget(db_path=None, parent=None) -> None`
**Garante:**
1. Inicializa em modo compacto (70px altura). Painel expandido tem 282px.
2. Timer de refresh a cada 5s para cotações.
3. Timer de eventos a cada ~5min (60 ciclos de 5s).
4. Barra de progresso do IBOV com gradiente vermelho→amarelo→verde.

### `conectar_fonte(source) -> None`
**Garante:**
1. Registra tópicos `BID`, `ASK`, `LAST_PRICE`, `CLOSE`, `VARIATION`, `OPEN` para cada código em `_gerar_defaults()`.

### `_atualizar_cotacoes() -> None`
**Garante:**
1. Lê CDI do banco (cache de 5min via `_ler_cdi`).
2. Para cada código default, lê preços do source e calcula variação (prioridade: `VARIATION` oficial → `(LAST - CLOSE)/CLOSE` → `(LAST - OPEN)/OPEN` → referência intraday).
3. Busca VIX via `yfinance` com cache de 60s.
4. Exibe no formato `Nome: valor ▲/▼+var%`.

### `_carregar_eventos_do_dia() -> None`
**Garante:**
1. Busca dividendos (`DividendoRepository.get_proximos(dias=1, dias_antes=1)`) e balanços (`CalendarioResultadosRepository.get_proximos(dias=1, dias_antes=1)`).
2. Eventos de hoje: cor viva. Eventos de ontem/amanhã: cor faded.
3. Se nenhum evento: mostra mensagem padrão.

### `_toggle() -> None`
**Garante:**
1. Expande/recolhe painel detalhado no duplo-clique.

### `mouseDoubleClickEvent(event) -> None`
**Garante:**
1. Chama `_toggle()`.

## Classes Auxiliares

### `TickerWidget`
**Garante:**
1. Letreiro com rolagem contínua da direita para a esquerda a ~35px/s.
2. Timer interno a 35ms (≈28 FPS).
3. Itens separados por "◆".
4. Cores: verde para proventos, amarelo para balanços, cinza para agenda vazia.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `datetime` | `date`, `timedelta` | Cálculo de contratos futuros vigentes |
| `PySide6.QtCore` | `Qt`, `QTimer`, `QRectF` | Timer de refresh e scroll |
| `PySide6.QtGui` | `QColor`, `QFont`, `QPainter`, `QPen` | Renderização do ticker e barra |
| `PySide6.QtWidgets` | `QFrame`, `QHBoxLayout`, `QLabel`, `QVBoxLayout`, `QWidget`, `QGridLayout`, `QProgressBar`, `QSizePolicy` | Layout da barra |
| `src.domain.services.market_data_source` | `FieldName` | Enum de campos RTD |
| `yfinance` | `yf` | VIX (import lazy em `_buscar_vix`) |
| `time` | — | Cache VIX (import lazy) |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository`, `DividendoRepository`, `CalendarioResultadosRepository` | CDI e eventos (import lazy) |

## Métricas

| Linhas | 494 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-08-06
- Os preços no painel expandido (ações BR, futuros, ADRs) são **hardcoded** no método `_setup_ui` — não são cotações reais. Ex: `"R$ 75,54"` para VALE3. Isso é intencional como placeholder visual ou é código legado não atualizado? **POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão**: os valores no painel expandido nunca são atualizados.
- O código de contrato futuro usa letras mensais B3 (`_MC`): F=Jan, G=Fev, H=Mar, J=Abr, K=Mai, M=Jun, N=Jul, Q=Ago, U=Set, V=Out, X=Nov, Z=Dez.
- `_contrato_bimestral_ativo` usa o dia 14 como corte para rolagem de contrato — data típica de vencimento de futuros B3.
- O campo `"Vetor: MISTO"` é hardcoded em `_atualizar_cotacoes` linha 409 — não usa o `MarketAnalyzer`. Isso difere do `SensibilidadeMercadoWidget` que calcula o vetor dinamicamente.
- `_buscar_vix` usa `yfinance` com `fast_info` — mais rápido que `info` mas pode não ter todos os campos em todos os tickers.
