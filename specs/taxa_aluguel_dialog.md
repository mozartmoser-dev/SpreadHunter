# TaxaAluguelDialog

Diálogo de visualização e atualização das taxas de aluguel de ações (BTC) coletadas do InvestSite. Exibe tabela com Ativo, Taxa Atual, Taxa 7d, Taxa 28d e Data. A atualização dispara o `ColetarTaxasAluguelUseCase` em thread separada com callback de progresso.

## Contrato (Requisitos)

### `TaxaAluguelDialog(db_path, parent=None) -> None`
**Garante:**
1. Tamanho inicial 650×500, mínimo 580×420.
2. Tabela com 5 colunas, ordenada alfabeticamente por ativo.
3. Botão "Atualizar" que inicia `_AtualizarThread`.
4. Label de status amarelo (visível durante coleta).

### `_carregar() -> None`
**Garante:**
1. Lê `TaxaAluguelRepository.get_latest_all()`.
2. Exibe taxas formatadas com 2 casas decimais e sufixo "%".
3. Data em formato ISO.

### `_atualizar() -> None`
**Garante:**
1. Desabilita botão, mostra "⏳ Coletando...".
2. Inicia `_AtualizarThread` com callback de progresso.
3. Ao concluir, recarrega dados e exibe resumo (sucessos/falhas).

## Classes Auxiliares

### `_AtualizarThread(QThread)`
**Garante:**
1. Instancia `ColetarTaxasAluguelUseCase` e chama `executar(callback_progresso=cb)`.
2. Emite `progress(corrente, total, ativo)` durante a coleta.
3. Emite `finished(resumo)` com dict `{status, sucessos, falhas, erros}`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtCore` | `Qt`, `Signal`, `QThread` | Thread e sinais |
| `PySide6.QtGui` | `QFont` | Fonte Consolas |
| `PySide6.QtWidgets` | Vários | UI |
| `src.infrastructure.persistence.repositories.repositories` | `TaxaAluguelRepository` | Leitura de taxas |
| `src.ui.desktop.theme` | `Palette` | Cores |
| `src.application.use_cases.coletar_taxas_aluguel` | `ColetarTaxasAluguelUseCase` | (Import lazy em `_AtualizarThread`) |

## Métricas

| Linhas | 189 |
| Testes | Não |

## Notas

- **Data da criação:** 2026-07-05
- Se a coleta estiver desabilitada (`taxa_aluguel_habilitado=0`), o use case retorna status "desabilitado" e o diálogo mostra warning.
- A thread `_AtualizarThread` captura exceções e as transforma em resumo de erro — o diálogo nunca quebra com exceção não tratada da thread.
- Se houver erro na coleta, `QMessageBox.critical` mostra apenas o primeiro erro (`erros[0]`). Erros subsequentes são suprimidos da UI.
