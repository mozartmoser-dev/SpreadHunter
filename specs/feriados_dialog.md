# FeriadosDialog

Diálogo de visualização e atualização do calendário de feriados da B3. Exibe tabela com Data, Feriado, Tipo (Nacional/SP), Fonte e Atualizado. Inclui calculadora CDI auxiliar (dias corridos → dias úteis → % CDI).

A atualização busca feriados via `FeriadosB3Provider` para anos alvo (ano anterior, corrente, próximo + anos existentes no banco).

## Contrato (Requisitos)

### `FeriadosDialog(db_path, parent=None) -> None`
**Garante:**
1. Tabela com 5 colunas, ordenável via `FeriadosSortProxy`.
2. ComboBox de filtro por ano (preenchido dinamicamente com anos disponíveis no banco).
3. Botão "Atualizar" que inicia `FeriadosFetchWorker` em QThread separada.
4. Calculadora CDI: spin de dias corridos → dias úteis (via `dc_to_du_aproximado`) → % CDI (DU/252 e DC/365).
5. Destaque visual: feriados de hoje com fundo verde escuro (#2d4a1e).

### `_atualizar_feriados() -> None`
**Garante:**
1. Determina anos alvo = `{ano_corrente-1, ano_corrente, ano_corrente+1}` ∪ anos já no banco.
2. Inicia `FeriadosFetchWorker` que deleta e reinsere feriados por ano.

## Classes Auxiliares

### `FeriadosTableModel(QAbstractTableModel)`
**Garante:**
1. Colunas: Data, Feriado, Tipo, Fonte, Atualizado.
2. Formata datas ISO → DD/MM/YYYY.
3. Tipos: "nacional" → "Nacional", "estadual_sp" → "SP (B3 fecha)".

### `FeriadosSortProxy(QSortFilterProxyModel)`
**Garante:**
1. Ordenação correta de datas ISO e strings.

### `FeriadosFetchWorker(QThread)`
**Garante:**
1. Para cada ano, chama `FeriadosB3Provider.buscar_feriados(ano)`.
2. `replace_feriados_ano(ano, feriados)` no repositório — DELETE + UPSERT na mesma transação.
3. Emite `progresso(atual, total, ano)`, `concluido(total, msg)`, `erro(msg)`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `datetime` | `date`, `datetime` | Formatação e data corrente |
| `PySide6.QtWidgets` | Vários | UI completa |
| `PySide6.QtCore` | `Qt`, `QAbstractTableModel`, `QThread`, `Signal`, `QSortFilterProxyModel` | Model e thread |
| `PySide6.QtGui` | `QFont`, `QColor`, `QBrush` | Estilização |
| `src.ui.desktop.theme` | `Palette` | Cores |
| `src.infrastructure.providers.feriados_b3_provider` | `FeriadosB3Provider` | (Import lazy em `FeriadosFetchWorker`) |
| `src.infrastructure.persistence.repositories.repositories` | `FeriadoB3Repository`, `ParametroRepository` | (Import lazy) |
| `src.domain.services.calendario_b3` | `dc_to_du_aproximado` | (Import lazy) |

## Métricas

| Linhas | 394 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-08-03
- `replace_feriados_ano(ano, feriados)` executa DELETE + UPSERT na mesma transação com rollback em caso de falha — a janela não-atômica foi fechada (commit `b679a6b`).
- O tipo "estadual_sp" é o único tipo regional documentado. Feriados municipais (ex: aniversário de São Paulo) não são cobertos.
- A calculadora CDI usa `dc_to_du_aproximado` do `calendario_b3` para conversão de dias corridos em dias úteis.
- `FeriadoB3Repository` e `FeriadosB3Provider` são importados lazy dentro de `FeriadosFetchWorker.run()` — isso evita dependências circulares e acelera o import inicial do módulo.
