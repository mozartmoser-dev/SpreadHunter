# pnt_utils

Utilitários para integração com o PNT (Profit Net Trade) — o sistema de ordens do Profit Pro. Fornece funções para formatar valores no padrão brasileiro e copiar baskets de ordens para o clipboard no formato esperado pelo PNT.

## Contrato (Requisitos)

### `copiar_basket_pnt(linhas) -> None`
**Garante:**
1. Junta as linhas com `\r\n` (CRLF, formato Windows esperado pelo PNT).
2. Seta no clipboard do sistema.

### `fmt_br(valor) -> str`
**Garante:**
1. Formata float com separador de milhar e 2 casas decimais no padrão brasileiro.
2. Exemplo: `1234.56` → `"1.234,56"`.
3. Técnica: formata com vírgula (inglês), troca `,` → `X`, `.` → `,`, `X` → `.`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QApplication` | Acesso ao clipboard |

## Métricas

| Linhas | 10 |
| Testes | Não |

## Notas

- **Data da criação:** 2026-06-16
- A técnica de dupla substituição em `fmt_br` (usando `X` como placeholder temporário) é um workaround comum para formatação brasileira sem depender de `locale`.
- `copiar_basket_pnt` não faz validação das linhas — assume que o chamador fornece linhas no formato correto para o PNT.
