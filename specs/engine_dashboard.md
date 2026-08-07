# EngineDashboard

Diálogo de monitoramento de saúde do motor de processamento. Exibe CPU, RAM, latência de scan, progresso de carga de instrumentos e status das ondas (Onda 1 = sensores leves, Onda 2 = foco com preços reais).

Diálogo frameless com cantos arredondados, arrastável (implementa `mousePressEvent`/`mouseMoveEvent`).

## Contrato (Requisitos)

### `EngineDashboard(parent=None) -> None`
**Garante:**
1. Tamanho fixo 500×480, frameless, fundo translúcido.
2. 4 `StatCard`: CPU Usage, Memory, Scan Latency, Engine Core.
3. Barra de progresso da carga de instrumentos (Onda 1 → Background Scan → Carga Concluída).
4. Label detalhado com: Database total, Sensors ativos, Registrados, Status da onda.

### `update_stats(stats: EngineStatsDTO) -> None`
**Garante:**
1. Atualiza CPU (1 casa decimal), RAM (inteiro MB), latência (ms).
2. Tooltip da latência inclui número real de instrumentos (formatado com separador de milhar BR).
3. Cor da latência: verde (<500ms), amarelo (<2000ms), vermelho (≥2000ms).
4. Barra de progresso: máximo = `total_instrumentos`, valor = `progresso_idx`.
5. Status text: "Carga Concluída" (progresso completo), "Background Scan" (registrado), "Onda 1 (Prioritários)" (inicial).

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `os` | — | Não usado diretamente no código visível |
| `psutil` | — | Não usado diretamente (provavelmente usado pelo chamador que popula `EngineStatsDTO`) |
| `PySide6.QtWidgets` | `QDialog`, `QVBoxLayout`, `QHBoxLayout`, `QLabel`, `QProgressBar`, `QFrame`, `QPushButton` | UI |
| `PySide6.QtCore` | `Qt`, `QTimer` | Flags de janela e timer |
| `PySide6.QtGui` | `QFont`, `QColor` | Não usado diretamente (importado mas cores são inline) |
| `src.ui.desktop.theme` | `Palette` | Importado mas não usado (cores são hardcoded) |
| `src.application.dtos.dtos` | `EngineStatsDTO` | DTO de entrada |

## Métricas

| Linhas | 247 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-06-29
- O card "Engine Core" mostra "NumPy Vec" fixo — não é atualizado por `update_stats`. Serve apenas como indicação visual de que o motor usa vetorização.
- `psutil` e `os` são importados mas não usados no escopo visível do arquivo. `EngineStatsDTO` é populado externamente (provavelmente no `MonitorWorker`).
- O tooltip da latência substitui vírgula por ponto para "padrão BR" (ex: `52.000` → `52.000`). Na verdade isso não é padrão BR — o separador de milhar BR é ponto, mas a substituição `replace(",", ".")` só funcionaria se o número original tivesse vírgula como separador de milhar, o que `:,` em f-string já produz.
- Implementa arraste da janela (frameless) via `mousePressEvent`/`mouseMoveEvent` com `_drag_pos`.
- O card `StatCard` é uma classe interna com tooltip via botão "i" estilizado como círculo.
