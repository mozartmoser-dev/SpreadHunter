# CalendarioResultadosCVM

Cliente HTTP para download de dados de resultados trimestrais (ITR/DFP) da CVM (Comissão de Valores Mobiliários). Baixa arquivos ZIP do portal de dados abertos, faz parse de CSVs dentro do ZIP e extrai eventos de publicação de resultados com mapeamento CNPJ → ticker.

## Contrato (Requisitos)

### `__init__()`
**Garante:**
1. Inicializa cache `_cache_cnpj_ticker` vazio.

### `set_cnpj_ticker_map(mapa: dict[str, str])`
**Garante:**
1. Popula o cache de mapeamento CNPJ → ticker.

### `buscar_itr(ano: int = 0) -> list[dict]`
**Garante:**
1. Se `ano == 0`, usa o ano atual.
2. Delega para `_buscar_do_zip` com a URL de ITR.

### `buscar_dfp(ano: int = 0) -> list[dict]`
**Garante:**
1. Se `ano == 0`, usa o ano atual.
2. Delega para `_buscar_do_zip` com a URL de DFP.

### `_buscar_do_zip(url: str, ano: int, tipo: str) -> list[dict]`
**Garante:**
1. Faz GET com timeout de 300s (arquivos ZIP podem ser grandes).
2. Se status != 200, loga warning e retorna `[]`.
3. Abre o ZIP em memória (`io.BytesIO`) e filtra CSVs com `"DRE_con"` ou `"DRE_ind"` no nome (Demonstração de Resultado — consolidado ou individual).
4. Para cada CSV, tenta decodificar com utf-8, latin-1 ou cp1252 (fallback: latin-1 com `errors="replace"`).
5. Faz parse com `csv.DictReader`, extraindo: `CNPJ_CIA` (cnpj), `DT_REFER` (data referência), `DENOM_SOCIAL` (nome empresa).
6. Deduplica por chave `"cnpj|dt_ref"`.
7. Mapeia CNPJ → ticker via `_cache_cnpj_ticker`.
8. Retorna lista de dicts com: `ativo`, `cnpj`, `nome_empresa`, `data_publicacao`, `trimestre_referencia`, `tipo_documento`, `tipo_evento="publicado"`, `fonte="cvm"`.

### `buscar_recentes(anos: int = 3) -> list[dict]`
**Garante:**
1. Itera do ano atual para trás por `anos` anos.
2. Para cada ano, busca ITR e DFP.
3. Retorna lista concatenada.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `csv` | `csv` | Parse de CSV |
| `io` | `io` | `BytesIO`, `StringIO` para buffers em memória |
| `logging` | `logging` | Logger |
| `zipfile` | `zipfile` | Leitura de ZIP |
| `datetime` | `date`, `datetime` | Datas |
| `requests` | `requests` | HTTP client |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 104 |
| Última modificação | 2026-07-05 |
| Classes | 1 (`CalendarioResultadosCVMProvider`) |

## Notas

- 2026-07-05 — última modificação.
- O mapeamento CNPJ → ticker depende de `set_cnpj_ticker_map()` ser chamado antes. Normalmente o `CalendarioResultadosRepository.get_cnpj_ticker_map()` popula esse cache a partir de dados já importados do webwallet.
- O timeout de 300s é necessário porque os ZIPs da CVM podem ser grandes (vários MB), especialmente anos com muitos balanços.
- A deduplicação por `"cnpj|dt_ref"` evita duplicatas entre DRE_con e DRE_ind para o mesmo CNPJ na mesma data.
- CSVs sem `DRE_con` ou `DRE_ind` no nome são ignorados (ex: balanço patrimonial, fluxo de caixa — não interessam para calendário de resultados).
