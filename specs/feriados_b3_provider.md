# FeriadosB3Provider

Cliente HTTP da Brasil API para consulta de feriados nacionais. Complementa com feriado estadual de SP (9 de Julho — Revolução Constitucionalista) que afeta o funcionamento da B3. Suporta busca em lote com callback de progresso.

## Contrato (Requisitos)

### `buscar_feriados(ano: int) -> list[dict]`
**Garante:**
1. Faz GET para `https://brasilapi.com.br/api/feriados/v1/{ano}` com timeout de 15s.
2. Se status 200, parseia JSON e retorna lista de `{data, nome, tipo, fonte}` com `fonte="brasilapi"`.
3. Se status != 200, loga warning e retorna lista vazia (não interrompe).
4. Após a chamada HTTP, sempre adiciona o feriado estadual de SP (9 de Julho) via `_adicionar_feriado_estadual_sp`.
5. Se a chamada HTTP falhar, ainda assim adiciona o feriado de SP (a lista base pode ser vazia, mas o feriado de SP é adicionado).

### `_adicionar_feriado_estadual_sp(feriados, ano)` (static)
**Garante:**
1. Adiciona `{data: "YYYY-07-09", nome: "Revolução Constitucionalista", tipo: "estadual_sp", fonte: "manual"}` se ainda não estiver na lista.
2. Reordena a lista por data.

### `buscar_varios_anos(anos: list[int], callback=None) -> list[dict]`
**Garante:**
1. Itera sobre anos ordenados, chamando `buscar_feriados` para cada.
2. Se `callback` fornecido, chama `callback(i+1, len(anos), str(ano))` para reportar progresso.
3. Retorna lista concatenada de todos os feriados.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `requests` | `requests` | HTTP client |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 60 |
| Última modificação | 2026-05-28 |
| Classes | 1 (`FeriadosB3Provider`) |

## Notas

- 2026-05-28 — última modificação.
- O feriado de 9 de Julho é adicionado manualmente porque a B3 fecha nessa data (feriado estadual de SP), mas a Brasil API só retorna feriados nacionais.
- O `callback` de progresso tem assinatura `(atual, total, ano_str)` — usado pela UI para mostrar barra de progresso durante importação.
- A Brasil API é gratuita e não requer autenticação.
