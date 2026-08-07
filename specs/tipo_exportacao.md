# TipoExportacao

Enum que discrimina os tipos de exportação suportados pelo `exportar_operacao.py`.
Define dois modos: exportação de basket ITM (cestas de opções) e log de operações.

## Contrato (Requisitos)

### `TipoExportacao` (enum)
**Garante:**
1. `BASKET_ITM = "BASKET_ITM"` — exportação de cestas de opções (call ITM + PUT + call ATM).
2. `LOG_OPERACAO = "LOG_OPERACAO"` — exportação de log de operações.
3. Valores são strings usadas como discriminador em `ExportarResultado.tipo_exportacao`.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| enum | `Enum` | Classe base |

**É dependência de:**
- `src/application/use_cases/exportar_operacao.py` — usa `TipoExportacao` como filtro/seletor
- `src/ui/desktop/export_dialog.py` — UI de exportação

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 3 (enum) / 227 (arquivo total) |
| Arquivo | `src/application/dtos/dtos.py` |
| Última modificação | 2026-07-29 |

## Notas
- Enum com apenas 2 membros. Se novos formatos de exportação forem adicionados (ex: CSV customizado), crescerá aqui.
- `TipoExportacao` e `ImportarResultado` coexistem no mesmo arquivo `dtos.py` por conveniência histórica — não há dependência entre eles.
