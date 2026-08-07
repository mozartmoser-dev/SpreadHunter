# MppTableModel

## Propósito

`QAbstractTableModel` para a tabela de ranking MPP (Motor de Priorização de Pescaria). Exibe 11 colunas com dados agregados de Box + MRE (Market Ranking Engine). Formatação simplificada sem ícones ou tachados — foco em scores numéricos e níveis de risco coloridos.

## Contrato (Requisitos)

### `atualizar(boxes: list, mres: list)`
**Garante:**
1. Hash composto de `(len(boxes), len(mres), id(boxes[0]), id(boxes[-1]), id(mres[0]), id(mres[-1]))`.
2. Constrói `mre_map` com chave `(ativo, strike1, strike2)` a partir da lista de MREs.
3. Para cada box, busca o MRE correspondente e monta dict com:
   - `ativo`, `box` ("K1xK2"), `score` (0-100), `nivel` (crítico/alto/médio/baixo)
   - `isca` (do MRE), `ip` (índice de pescabilidade × 100), `lote` (sugerido)
   - `confianca` (formato %), `persistencia` (com sufixo "c"), `spread` (formato %), `prof_qtd`
4. Preserva referências originais em `_box` e `_mre` para acesso posterior.

### `data(index, role)`
**Garante:**
1. **DisplayRole:** Todos os valores como string.
2. **TextAlignmentRole:** Alinhamento à direita para colunas numéricas (score, ip, confianca, lote, persistencia, spread, prof_qtd).
3. **ForegroundRole:** Vermelho (#ef4444) para nível "crítico", laranja (#f59e0b) para "alto", ciano (#22d3ee) para "médio".
4. **Sem BackgroundRole, FontRole, DecorationRole.**

### `get_box(row)` / `get_mre(row)`
**Garante:**
1. Retorna a referência original do box/MRE ou None se índice inválido.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtCore` | `QAbstractTableModel, Qt` | Modelo Qt |
| `PySide6.QtGui` | `QColor` | Cores de nível |

## Métricas

| Linhas | 119 |
| Classes | 1 |
| Testes | Não |

## Notas

- **Sem `headerData` tooltips individuais por coluna** (apenas `COLUMN_TOOLTIPS` definido como dicionário no módulo, mas o `headerData` não o referencia — usa apenas `DisplayRole`). POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: tooltips declarados mas não aplicados.
- **Nível de risco com acentos:** "crítico", "médio" — podem causar problemas em sistemas sem suporte a UTF-8 no terminal, mas a UI Qt suporta.
- **Modelo mais simples** — sem hash de otimização com `_ultimo_hash` (sempre reconstrói tudo em `atualizar`).
