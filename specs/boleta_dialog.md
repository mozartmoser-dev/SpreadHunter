# BoletaDialog

## Propósito

Diálogo de basket PNT MultiLeg — gera a boleta de montagem para envio ao Profit Pro (PNT). Suporta 8 estratégias (BOX, SBTH, BOXSBTH, COLAR, COLAR_CALENDARIO, PUT_RATIO, VENDA_COBERTA, TAXA). Exibe tabela de pernas com quantidade, profundidade de book, quantidade apregoada. Suporte a acumulação de múltiplos baskets. Botão "Monta no PNT" que executa automação via `pyautogui`.

## Contrato (Requisitos)

### `__init__(strategy, r, db_path, parent)`
**Garante:**
1. Lê parâmetros do banco: `qtd_acoes_boleta`, `lote_padrao`, `qtd_apregoada`.
2. Configura título da janela: "Boleta Basket — {strategy}".
3. Chama `_montar_pernas()` para preencher a tabela de acordo com a estratégia.

### `_montar_pernas()`
**Garante:**
1. Para cada estratégia, gera as pernas corretas com lado (Compra/Venda), quantidade, e código do ativo:
   - **BOX:** Compra CALL K1, Vende PUT K1, Vende CALL K2, Compra PUT K2 + Coeficiente (Spread).
   - **SBTH:** Compra Ativo, Compra PUT, Vende CALL.
   - **COLAR:** Compra Ativo, Compra PUT, Vende CALL.
   - **COLAR_CALENDARIO:** Compra PUT longa, Vende PUT curta (ou CALL, dependendo do tipo).
   - **PUT_RATIO:** Compra PUT K1 (N1×), Vende PUT K2 (N2×).
   - **VENDA_COBERTA:** Vende Ativo (bid), Compra CALL (ask).
   - **TAXA:** Compra Ativo (ask), Vende CALL (bid).
2. Exibe coeficiente (spread financeiro da estrutura) no label `lbl_coeficiente`.
3. Mostra data/hora de detecção (Brasília) no rodapé.

### `_copiar()`
**Garante:**
1. Copia basket formatado para clipboard via `copiar_basket_pnt()`.
2. Formato: linhas de "Ativo;Lado;Quantidade;Preço;Ordem" separadas por `\r\n`.

### `_montar_pnt()`
**Garante:**
1. Executa `executar_automacao_pnt(basket_str, db_path)` — automação via pyautogui que digita as pernas no Profit Pro.
2. Exibe QMessageBox de confirmação ou erro.

### Acumulação de baskets
**Garante:**
1. Checkbox "Acumular baskets" — ao marcar, cada boleta gerada é adicionada ao acumulador global `_ACCUMULATOR`.
2. Tabela de acumulados (`tbl_acumulo`) mostra estratégia, pernas e coeficiente de cada basket acumulado.
3. Botão "Limpar" esvazia o acumulador.
4. Botão "Copiar TUDO" copia todos os baskets acumulados de uma vez.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QDialog, QVBoxLayout, ..., QCheckBox` | UI framework |
| `PySide6.QtCore` | `Qt, QTimer` | Timer |
| `PySide6.QtGui` | `QFont` | Fonte |
| `src.infrastructure.persistence.database` | `get_db_path` | Path do banco |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Parâmetros |
| `src.ui.desktop.theme` | `Palette` | Cores |
| `src.ui.desktop.pnt_utils` | `copiar_basket_pnt, fmt_br` | Formatação PNT |
| `src.infrastructure.integrations.pnt` | `executar_automacao_pnt` | Automação Profit Pro |

## Métricas

| Linhas | 366 |
| Classes | 1 |
| Testes | Não |

## Notas

- **`_ACCUMULATOR` global:** Lista no nível do módulo — sobrevive ao fechamento do diálogo. Acumula baskets entre múltiplas aberturas do `BoletaDialog`. Isso permite montar múltiplos baskets e enviá-los juntos ao PNT.
- **`QTD_APREGoada`** (com "G" maiúsculo): Constante 100 — typo no nome da variável, mas consistente com o uso na interface.
- **Automação PNT via pyautogui:** `executar_automacao_pnt` envia keystrokes para o Profit Pro. Frágil — depende de o Profit estar aberto e na janela correta.
- **Detecção de timezone:** Usa `zoneinfo.ZoneInfo("America/Sao_Paulo")` — requer Python 3.9+.
- **Copiar Debug:** Botão que copia timestamps, preço ativo, recebimento, ganho, CDI, PUT/CALL book e `label_detectado` para clipboard. Diagnóstico de cotação.
