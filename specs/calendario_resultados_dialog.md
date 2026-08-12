# CalendarioResultadosDialog

Diálogo de visualização e atualização da agenda de resultados (balanços) de empresas B3. Exibe tabela com Ativo, Empresa, Data, Trimestre, Tipo, Evento e Fonte. A atualização busca dados via `CalendarioResultadosWebwalletProvider`.

## Contrato (Requisitos)

### `CalendarioResultadosDialog(db_path, parent=None) -> None`
**Garante:**
1. Tamanho mínimo 1000×500.
2. Tabela com 7 colunas, ordenável via `CalendarioSortProxy`.
3. ComboBox de filtro: Todos, Previstos (próx. 60d), Publicados.
4. Botão "Atualizar" que inicia `CalendarioFetchWorker`.

### `carregar_dados() -> None`
**Garante:**
1. Lê `CalendarioResultadosRepository.get_all()`.
2. Aplica filtro atual.

### `_aplicar_filtro() -> None`
**Garante:**
1. "Previstos (próx. 60d)": filtra `tipo_evento == "previsto"` com `data_publicacao` entre hoje e hoje+60d.
2. "Publicados": filtra `tipo_evento == "publicado"`.
3. "Todos": sem filtro.

### `_atualizar_resultados() -> None`
**Garante:**
1. Inicia `CalendarioFetchWorker` que deleta por fonte "webwallet" e insere novos previstos.
2. Ao concluir, recarrega dados.

## Classes Auxiliares

### `CalendarioTableModel(QAbstractTableModel)`
**Garante:**
1. Colunas: Ativo, Empresa, Data, Trimestre, Tipo, Evento, Fonte.
2. Cores: evento "publicado" = verde, outros = laranja.
3. Fundo condicional para previstos de hoje.

### `CalendarioSortProxy(QSortFilterProxyModel)`
**Garante:**
1. Ordenação tipada (int/float vs string).

### `CalendarioFetchWorker(QThread)`
**Garante:**
1. Chama `CalendarioResultadosWebwalletProvider.buscar_todos()`.
2. `replace_by_fonte("webwallet", previstos)` — DELETE + UPSERT na mesma transação.
3. Emite `progresso`, `concluido`, `erro`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `datetime` | `datetime`, `timedelta` | Filtro de data |
| `PySide6.QtWidgets` | Vários | UI |
| `PySide6.QtCore` | `Qt`, `QAbstractTableModel`, `QThread`, `Signal`, `QSortFilterProxyModel` | Model e thread |
| `PySide6.QtGui` | `QFont`, `QColor`, `QBrush` | Estilização |
| `src.ui.desktop.theme` | `Palette` | Cores |
| `src.infrastructure.providers.calendario_resultados_webwallet` | `CalendarioResultadosWebwalletProvider` | (Import lazy) |
| `src.infrastructure.persistence.repositories.repositories` | `CalendarioResultadosRepository` | (Import lazy) |

## Métricas

| Linhas | 321 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-07-29
- `CalendarioFetchWorker` deleta por fonte "webwallet" antes de inserir — mesmos dados de outras fontes (ex: CVM) não são afetados.
- A barra de progresso tem máximo fixo 2 (passo 1: "Webwallet (previstos)...", passo 2: "Finalizando..."). Não reflete o progresso real da operação.
- `replace_by_fonte("webwallet", previstos)` executa DELETE + UPSERT na mesma transação com rollback — a janela não-atômica foi fechada (commit `b679a6b`).
- O diálogo não tem tratamento para quando o provider retorna lista vazia (`previstos = []`) — simplesmente deleta tudo da fonte e insere nada, efetivamente limpando os dados.
