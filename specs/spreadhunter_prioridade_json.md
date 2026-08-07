# spreadhunter_prioridade.json

Arquivo de cache de prioridade de instrumentos. Contém uma lista de códigos de opções
(prefixo B3) que já tiveram book de mercado ativo em execuções anteriores. Usado pelo
`mercado_data_provider.py` para priorizar o registro/assinatura de instrumentos que
historicamente têm liquidez, reduzindo o tempo até o primeiro dado útil.

## Contrato (Requisitos)

### Formato
**Garante:**
1. Array JSON de strings — cada string é um código de opção B3 (ex: `"ITSAN165"`, `"ITUBS484W2"`).
2. Nem todos os códigos têm o prefixo de ativo explícito — a chave composta
   `f"{ativo}|{codigo}"` é usada em alguns contextos, mas o arquivo contém apenas
   códigos puros (sem `|`).

### Uso no `mercado_data_provider.py`
**Garante:**
1. **Leitura** (`_carregar_prioridades`):
   - Resolve caminho: `<db_path sem ext>.pri` → `spreadhunter_prioridade.json`
     (na prática `<base>_prioridade.json` onde `base` = `spreadhunter`).
   - Se o arquivo existe, carrega como `set[str]`.
   - Se não existe, retorna `set()` vazio.
2. **Escrita** (`_salvar_prioridades`):
   - Salva todas as chaves com dados no cache + chaves com book conhecido.
   - Formato: `json.dump(list(chaves), f)`.
3. **Uso no pipeline**: instrumentos no conjunto de prioridade são processados primeiro
   na onda 1 (carga inteligente), antes dos demais.

### Localização
**Garante:**
1. Resolvido a partir de `db_path`: `os.path.splitext(str(db_path))[0] + "_prioridade.json"`.
2. Em produção: `%APPDATA%/Spreadhunter/spreadhunter_prioridade.json`.
3. O arquivo em `config/spreadhunter_prioridade.json` é uma seed inicial (pré-populada
   com ~190+ instrumentos de alta liquidez: ITUB, ITSA, WEGE, ABEV, ALOS).

## Dependências Diretas (por import)
| Módulo | Uso |
|---|---|
| `src/infrastructure/providers/mercado_data_provider.py` | `_carregar_prioridades()`, `_salvar_prioridades()`, `_resolver_caminho_prioridade()` |

**Nenhum arquivo Python referencia `spreadhunter_prioridade.json` pelo nome literal** —
a resolução é dinâmica via `_resolver_caminho_prioridade()` que deriva o nome do `db_path`.

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 1 (array JSON em linha única) |
| Tamanho | ~3.5KB (190+ instrumentos) |
| Arquivo | `config/spreadhunter_prioridade.json` |
| Última modificação | 2026-06-25 |

## Notas
- 2026-06-25: última (e única) modificação registrada no git.
- O arquivo é sobrescrito em runtime por `_salvar_prioridades()` — o conteúdo em `config/`
  é apenas a seed inicial. Em produção, o arquivo ativo está em `%APPDATA%/Spreadhunter/`.
- A lista contém instrumentos que já expiraram — não há mecanismo de limpeza de vencimentos
  passados. O arquivo cresce monotonicamente.
- Formato de linha única (sem pretty-print) — difícil de inspecionar manualmente.
