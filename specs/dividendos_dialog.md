# DividendosDialog

Diálogo de visualização e atualização da agenda de proventos (dividendos, JCP, etc.). Exibe tabela com Ativo, Tipo, Data COM, Pagamento, Valor e Atualizado. A atualização busca proventos via `DividendosStatusInvestProvider` para todos os ativos na base de instrumentos.

## Contrato (Requisitos)

### `DividendosDialog(db_path, parent=None) -> None`
**Garante:**
1. Tabela com 6 colunas, ordenável via `DividendosSortProxy`.
2. ComboBox de filtro: Todos, Hoje, Amanhã, Próx. 7 dias, Próx. 30 dias.
3. ComboBox de ordenação: Data COM ↓/↑, Ativo A-Z, Valor ↓.
4. Botão "Atualizar" que varre todos os ativos da base (`InstrumentoRepository.get_all()`).
5. Destaque visual: Data COM de hoje = fundo verde escuro, amanhã = fundo amarelo escuro.

### `_atualizar_proventos() -> None`
**Garante:**
1. Obtém ativos únicos da base de instrumentos.
2. Se base vazia, exibe aviso e retorna.
3. Inicia `DividendosFetchWorker` em QThread separada.

### `_aplicar_filtro() -> None`
**Garante:**
1. Filtra por data COM (hoje, amanhã, 7d, 30d) usando comparação ISO.
2. Ordena conforme seleção do usuário (data, ativo, valor).

## Classes Auxiliares

### `DividendosTableModel(QAbstractTableModel)`
**Garante:**
1. Colunas: Ativo, Tipo, Data COM, Pagamento, Valor, Atualizado.
2. Formata datas ISO → DD/MM/YYYY.
3. Valor formatado com 6 casas decimais.
4. Destaque condicional: fundo verde para data COM = hoje, amarelo para amanhã.

### `DividendosSortProxy(QSortFilterProxyModel)`
**Garante:**
1. Ordenação correta de datas ISO e valores numéricos.

### `DividendosFetchWorker(QThread)`
**Garante:**
1. Para cada ativo, chama `DividendosStatusInvestProvider.buscar_proventos(ativo)`.
2. `save_batch` no `DividendoRepository`.
3. Emite `progresso(atual, total, ativo)`, `concluido(total, msg)`, `erro(msg)`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `datetime` | `datetime`, `timedelta` | Filtro de data e formatação |
| `PySide6.QtWidgets` | Vários | UI |
| `PySide6.QtCore` | `Qt`, `QAbstractTableModel`, `QDate`, `QThread`, `Signal`, `QSortFilterProxyModel` | Model e thread |
| `PySide6.QtGui` | `QFont`, `QColor`, `QBrush` | Estilização |
| `src.ui.desktop.theme` | `Palette` | Cores |
| `src.infrastructure.providers.dividendos_statusinvest` | `DividendosStatusInvestProvider` | (Import lazy) |
| `src.infrastructure.persistence.repositories.repositories` | `DividendoRepository`, `InstrumentoRepository` | (Import lazy) |

## Métricas

| Linhas | 390 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-06-16
- `DividendosFetchWorker` aceita parâmetro `modo` no construtor ("rapida" ou "completa") mas não usa essa informação — `provider.buscar_proventos(ativo)` é chamado da mesma forma independente do modo.
- A atualização varre TODOS os ativos da base (sem opção de selecionar subset), o que pode ser demorado para bases grandes (500+ ativos).
- `save_batch` é chamado para cada ativo individualmente (não em lote), o que gera múltiplas transações. Pode ser lento para muitos ativos.
- O ComboBox de ordenação armazena `(chave, desc)` como `userData` — `True` para descendente, `False` para ascendente.
- `QDate` é importado mas não usado no código visível.
