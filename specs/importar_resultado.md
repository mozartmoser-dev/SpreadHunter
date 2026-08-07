# ImportarResultado

DTO que representa o resultado de uma operação de importação de séries de opções.
Transporta a contagem de instrumentos importados, removidos (blacklist) e a lista
de ativos afetados.

## Contrato (Requisitos)

### `ImportarResultado(total_importados, total_removidos, ativos)`
**Garante:**
1. `total_importados: int` — número de instrumentos inseridos no banco.
2. `total_removidos: int` — número de instrumentos removidos (blacklist).
3. `ativos: list[str]` — lista de códigos de ativos presentes na importação (default `[]`).
4. `slots=True` — não aceita atributos extras em runtime.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| dataclasses | `dataclass`, `field` | Decorador + default factory |
| datetime | `date`, `datetime` | Tipos (usados por outras classes no mesmo arquivo) |
| enum | `Enum` | Usado por `TipoExportacao` no mesmo arquivo |

**É dependência de:**
- `importflash.py` (constroi `ImportarResultado` ao final da importação)
- Testes que validam importação

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 15 (classe) / 227 (arquivo total) |
| Arquivo | `src/application/dtos/dtos.py` |
| Última modificação | 2026-07-29 |

## Notas
- DTO puro, sem lógica de negócio. `slots=True` indica uso intensivo em loops de varredura.
- `ImportarResultado` não tem dependências sobre outras classes do projeto — apenas stdlib.
