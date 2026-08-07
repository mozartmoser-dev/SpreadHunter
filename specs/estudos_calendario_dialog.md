# EstudosCalendarioDialog

Diálogo avançado para comparação de otimizações de Collar Calendário por estágio (Base, Platô, Proteção, Rendimento). Exibe tabela com 25 colunas de métricas (breakevens, PnL em caudas, sigma, valor esperado, etc.), gráficos de payoff interativos, dashboard de comparação multi-estágio com 6 painéis matplotlib (CDI, PnL, BE, Stress-Test, Radar, Delta PnL), e tabela de comparação lado a lado.

Lê dados diretamente da tabela `historico_simulacoes` no SQLite (não usa repositório).

## Contrato (Requisitos)

### `EstudosCalendarioDialog(parent=None) -> None`
**Garante:**
1. Tamanho inicial 1200×600, maximizável.
2. Tabela com 25 colunas definidas em `COLUMNS`.
3. Colunas arrastáveis com persistência via `column_utils` (chave `estudos_calendario_order`).
4. Botões: Explicar, Comparar Otimizações, Dashboard, Recarregar, Limpar Estudos, Fechar.

### `_carregar() -> None`
**Garante:**
1. Lê `SELECT * FROM historico_simulacoes ORDER BY detectado_em DESC, estagio`.
2. Para cada linha, calcula campos derivados: BE strings, quantidades (ratio × qtd_acao), sigmas nominais (distância ÷ one_sigma), piso 2σ.
3. Atualiza título da janela com contagem de registros e chassis.

### `_explicar_selecionado() -> None`
**Garante:**
1. Reconstrói `ResultadoColarCalendario` a partir dos dados da linha.
2. Chama `CalculadoraColarCalendario.gerar_explicacao(r, r.r)`.
3. Exibe em diálogo com `QTextEdit` HTML.

### `_comparar_estagios_chassi() -> None`
**Garante:**
1. Busca todas as linhas do mesmo `id_chassi`.
2. Exibe tabela comparativa com 17 métricas (Ratio, PnL, %CDI, BE, Cauda, Sigma, BWB).
3. Destaca melhor (verde) e pior (vermelho) valor de cada métrica.
4. Inclui linha Δ PnL vs Base.

### `_abrir_dashboard(ativo, id_chassi, records, estagios_order) -> None`
**Garante:**
1. Gera figura matplotlib 3×2 com 6 painéis: CDI (barras horizontais), PnL Líquido, Amplitude de Breakeven, Stress-Test de Cauda (±nσ), Radar de Perfil Comparativo (polar), Δ PnL vs Base.
2. Radar normaliza 5 métricas (Retorno, PnL, Cobertura Cauda Dir, Estreito BE, Baixo Custo) para escala 0-1.
3. Lê `otimizado_desvios_sigma` do banco para título do stress-test.
4. Exibe em diálogo com `FigureCanvasQTAgg`.

### `_plot_payoff(r) -> None`
**Garante:**
1. Calcula payoff do Collar Calendário com: stock PnL (min(x, Kc) - S_custo), call PnL, naked call PnL, put PnL (Black-Scholes se T_rem > 0, intrínseco caso contrário).
2. Se existirem BWB strikes históricos (`strikes_bwb_call`/`strikes_bwb_put`), adiciona PnL da borboleta.
3. Gráfico com gradiente verde/vermelho por trecho, linhas de BE, strikes e spot.
4. Footer com detalhes da montagem (preços, quantidades, capital, PnL projetado, BWB info).

### `_limpar_estudos() -> None`
**Garante:**
1. Confirmação via `QMessageBox.question`.
2. `DELETE FROM historico_simulacoes` direto no SQLite.
3. Recarrega dados.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `logging` | — | Logs |
| `sqlite3` | — | Leitura/escrita direta no banco |
| `math` | `sqrt` | Cálculo de sigma |
| `pathlib` | `Path` | Importado mas não usado |
| `PySide6.QtWidgets` | Vários | UI |
| `PySide6.QtCore` | `Qt`, `QAbstractTableModel`, `QTimer` | Model e timer |
| `PySide6.QtGui` | `QFont`, `QColor` | Estilização |
| `src.domain.services.calendario_b3` | `dc_to_du` | Conversão DC→DU |
| `src.infrastructure.persistence.database` | `get_db_path` | Caminho do banco |
| `src.ui.desktop.column_utils` | `salvar_ordem_colunas`, `limpar_e_restaurar_colunas` | Persistência de colunas |
| `numpy` | `np` | (Import lazy em `_abrir_dashboard`) |
| `matplotlib` | `FigureCanvasQTAgg`, `Figure`, `GridSpec` | (Import lazy) |
| `scipy.stats` | `norm` | Black-Scholes (import lazy em `_plot_payoff`) |
| `src.domain.services.calculadora_colar_calendario` | `CalculadoraColarCalendario`, `ResultadoColarCalendario`, `TipoColarCalendario` | (Import lazy) |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | (Import lazy) |
| `src.ui.desktop.copy_utils` | `salvar_figura_arquivo`, `copiar_figura_clipboard` | (Import lazy) |
| `src.ui.desktop.theme` | `Palette` | (Import lazy) |
| `zoneinfo` | `ZoneInfo` | Timezone (import lazy em `data()`) |

## Métricas

| Linhas | 1017 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-08-03
- Este é o maior e mais complexo diálogo da UI (1017 linhas). Combina tabela, múltiplos gráficos matplotlib, análise de payoff com Black-Scholes, e BWB (Butterfly with Body).
- `_carregar` lê direto do SQLite com `sqlite3.connect` — não usa `HistoricoSimulacoesRepository`. Isso é intencional para performance (evita a camada de repositório para queries analíticas) mas quebra o padrão de acesso a dados do resto do sistema.
- Os estágios de otimização são: Base (original), Platô (simetria), Proteção (sem BE esquerdo), Rendimento (maior range). Estágios com "+Tail" indicam que proteção BWB foi aplicada.
- `_abrir_dashboard` e `_abrir_dashboard_selecionado` têm lógica duplicada para montar `records` a partir do banco.
- O radar chart usa `projection='polar'` do matplotlib — requer matplotlib >= 3.0.
- `_plot_payoff` implementa Black-Scholes manualmente para calcular o valor da PUT no vencimento da CALL (perna remanescente do calendário). Usa `scipy.stats.norm.cdf`.
- BWB strikes são armazenados como string CSV no banco (`"w1,k_body,w2"`) e parseados com `map(float, ...)`. Se o parse falhar, o BWB é silenciosamente ignorado.
- O diálogo acessa o banco diretamente em múltiplos pontos (`_carregar`, `_comparar_estagios_chassi`, `_abrir_dashboard_selecionado`, `_limpar_estudos`) — cada um abre sua própria conexão. Não há pool ou reuso de conexão.
