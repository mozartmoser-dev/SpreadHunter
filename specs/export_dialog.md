# ExportDialog

## Propósito

Diálogo de exportação de operação — visualiza e confirma os dados de uma `OportunidadeMonitor` antes de registrá-la ou exportá-la como basket. Três abas: Pernas & Custos, Dados de Mercado, Operação. Suporta registro no banco (`Registrar Operação`) e exportação formatada para clipboard (`Exportar BASKET ITM`). Verifica data ex-dividendo e alerta se o vencimento da operação cruzar com proventos.

## Contrato (Requisitos)

### `__init__(oportunidade, use_case, parent, db_path, source)`
**Garante:**
1. Valida e formata data de vencimento (DD/MM/YYYY com DTE).
2. Chama `_verificar_ex_dividendo()` para checar proventos.
3. Header exibe: Ativo | Tipo | Strike | Vencimento (DTE).

### Aba "Pernas & Custos"
**Garante:**
1. Exibe as 3 pernas: Compra Ativo (com preço ask), Compra PUT (com strike), Venda CALL (com strike).
2. Mostra custos Box e SBTH com tachado para o tipo não aplicável (ex: custo Box tachado se a operação é SBTH).
3. Indicador de data/hora de detecção (Brasília).

### Aba "Dados de Mercado"
**Garante:**
1. Exibe book: ofertas de compra/venda, quantidades, preço do ativo, strike.
2. Informações de liquidez por perna.
3. Taxa de aluguel (BTC) se disponível.

### Aba "Operação"
**Garante:**
1. Formulário para dados operacionais: quantidade de ações, lote padrão, preço de execução (editável).
2. Cálculos finais: custo total, rentabilidade projetada, CDI equivalente.
3. Botões de ação: "Registrar Operação" e "Exportar BASKET ITM".

### `_exportar_log()`
**Garante:**
1. Chama `ExportarOperacaoUseCase.exportar(oportunidade, tipo_exportacao)` com `TipoExportacao.LOG`.
2. Registra a operação no banco de dados (tabela `operacoes`).
3. Exibe QMessageBox de sucesso/erro.

### `_exportar_basket()`
**Garante:**
1. Chama `ExportarOperacaoUseCase.exportar(oportunidade, tipo_exportacao)` com `TipoExportacao.BASKET_ITM`.
2. Gera string formatada no padrão ITM (In The Money) para clipboard.

### `_verificar_ex_dividendo()`
**Garante:**
1. Consulta proventos do ativo no banco (via repositório de dividendos).
2. Se houver data ex no período até o vencimento, exibe alerta visual (label amarelo/vermelho).
3. Alerta inclui: data ex, valor do provento, impacto estimado.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QApplication, QDialog, ..., QWidget` | UI framework |
| `PySide6.QtCore` | `Qt` | Alinhamento |
| `PySide6.QtGui` | `QFont` | Fonte |
| `src.application.dtos.dtos` | `OportunidadeMonitor, TipoExportacao` | DTOs |
| `src.application.use_cases.exportar_operacao` | `ExportarOperacaoUseCase` | Use case |
| `src.ui.desktop.theme` | `Palette` | Cores |

## Métricas

| Linhas | 462 |
| Classes | 1 |
| Testes | Não (testado indiretamente via `test_fase3.py`) |

## Notas

- **Tachado condicional:** Labels de custo/ganho do tipo não aplicável (ex: custo Box em operação SBTH) recebem fonte com `setStrikeOut(True)` e cor `STRIKEOUT_COLOR`.
- **Formatação de data com fallback:** Tenta `strftime`, depois parsing de DD/MM/YYYY, depois ISO 8601, depois `str()` puro.
- **`_source` passado mas uso não visível:** O parâmetro `source` (fonte de market data) é armazenado em `self._source` mas seu uso não está visível no trecho lido. Provavelmente usado para queries adicionais de book na aba de mercado.
- **Verificação ex-dividendo:** Funcionalidade crítica — se uma operação cruzar uma data ex-dividendo, o valor do provento afeta o preço da ação e pode invalidar a arbitragem.
- **Copiar Debug:** Botão que copia timestamps, preço ativo, PUT/CALL book, classificação, custos e `label_detectado` para clipboard. Útil para diagnóstico de STALE e validação de cotação.
- **Timestamp no label:** O preço do ativo exibe sufixo com idade (`(preço Xs atrás)`) quando stale > 10s, com destaque amarelo.
