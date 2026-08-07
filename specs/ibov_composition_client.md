# IbovCompositionClient

Cliente para composição do IBOV (Ibovespa). Carrega lista de tickers com pesos a partir de um arquivo JSON de configuração, com fallback para uma lista hardcoded dos top-15. Calcula peso acumulado e corte nos 50%.

## Contrato (Requisitos)

### `__init__(config_path=None)`
**Garante:**
1. Armazena `config_path` opcional.

### `get_top50_percent() -> list[dict]`
**Garante:**
1. Usa cache de classe (`_cache`).
2. Carrega dados via `_carregar()`.
3. Filtra apenas itens onde `corte == False` (peso acumulado < 50%).
4. Retorna lista de `{ticker, peso, acum, corte}`.

### `get_all() -> list[dict]`
**Garante:**
1. Usa cache de classe (`_cache`).
2. Retorna todos os itens (sem filtrar por corte).

### `_carregar() -> list[dict]`
**Garante:**
1. Se `config_path` existe, carrega JSON do arquivo.
2. Se o JSON é uma lista válida, calcula pesos acumulados via `_pesos_acumulados`.
3. Fallback: usa `_IBOV_TOP50_DEFAULT` (15 tickers hardcoded com pesos aproximados).
4. Aplica `_pesos_acumulados` em ambos os casos.

### `_pesos_acumulados(items) -> list[dict]` (função módulo)
**Garante:**
1. Calcula peso acumulado progressivo.
2. Adiciona campo `acum` (acumulado arredondado) e `corte` (True se acumulado >= 50%).

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `__future__` | `annotations` | Type hints |
| `json` | `json` | Leitura de arquivo de configuração |
| `logging` | `logging` | Logger |
| `os` | `os` | `os.path.exists` para verificar config |
| `typing` | `NamedTuple` | Importado mas não usado como classe |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 69 |
| Última modificação | 2026-07-14 |
| Classes | 1 (`IbovCompositionClient`) |

## Notas

- 2026-07-14 — última modificação.
- O cache é de classe (`_cache`), não de instância — todas as instâncias compartilham. Se `config_path` mudar entre instâncias, o cache ainda retorna o primeiro valor carregado.
- `NamedTuple` é importado mas não usado — possível leftover de refatoração.
- A lista hardcoded `_IBOV_TOP50_DEFAULT` contém pesos aproximados (não atualizados em tempo real). O arquivo JSON de configuração permite atualização manual.
- O conceito de "top 50%" é relevante para priorização de ativos no scanner — ativos que representam 50% do IBOV recebem prioridade.
