# ExcelImporter

Utilitário para parsing de dados de importação de planilhas Excel. Fornece funções para sanitização de strike (correção de escala) e extração de vencimento a partir de formatos comuns de data.

## Contrato (Requisitos)

### `sanitizar_strike(valor_bruto: float, preco_ref: float) -> float`
**Garante:**
1. Se `preco_ref` ou `valor_bruto` é <= 0, retorna `valor_bruto` inalterado.
2. Testa divisores `[0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]` para encontrar a escala correta do strike.
3. Para cada divisor, calcula `razao = (valor_bruto / d) / preco_ref`.
4. Se `razao < 0.1` ou `razao > 3.0`, aplica penalidade de 10.0 ao score.
5. Score = `abs(log(razao)) + penalidade`.
6. Retorna o strike com o menor score.

### `extrair_strike(codigo: str, preco_ref: float | None = None) -> float | None`
**Garante:**
1. Extrai números do final do código via regex `(\d+)[a-zA-Z]?$`.
2. Se `preco_ref` fornecido, delega para `sanitizar_strike`.
3. Sem `preco_ref`, aplica heurística: 1-2 dígitos = valor direto, 3 dígitos = /10, 4 dígitos = /10, 5+ dígitos = /1000.
4. Retorna `None` se não encontrar números ou o parse falhar.

### `parse_vencimento(val) -> date | None`
**Garante:**
1. Aceita `None`, `datetime`, `date` ou `str`.
2. Se `datetime`, extrai `.date()`.
3. Se `date`, retorna como está.
4. Se `str`, tenta formatos `"%d/%m/%Y"` e `"%Y-%m-%d"`.
5. Retorna `None` se não conseguir parsear.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `re` | `re` | Extração de números do código |
| `math` | `math` | `log` para score de escala |
| `datetime` | `date`, `datetime` | Parsing de datas |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 66 |
| Última modificação | 2026-07-02 |
| Classes | 0 (módulo de funções) |

## Notas

- 2026-07-02 — última modificação.
- `sanitizar_strike` resolve o problema clássico de strikes em Excel: valores como `1845` podem ser R$18.45 (escala 100) ou R$1.845 (escala 1000). A heurística usa o preço de referência para determinar a escala correta.
- A penalidade de 10.0 para razões fora de `[0.1, 3.0]` é um hack para descartar escalas absurdas (ex: strike 100× o preço).
- `extrair_strike` sem `preco_ref` usa heurísticas baseadas no número de dígitos, que podem falhar para casos ambíguos (ex: código com 3 dígitos onde o strike real é centenas, não dezenas).
