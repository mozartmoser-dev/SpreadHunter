# ParametroOperacional

## Propósito

Entidade que representa um parâmetro de configuração do sistema (chave-valor)
persistido no banco e categorizado por estratégia. É a base do sistema de
parametrização obrigatória (regra #3 do AGENTS.md): TODO valor de negócio
deve vir do banco via `ParametroRepository.get_by_chave()`, nunca hardcoded.

Fornece um conjunto de defaults (`PARAMETROS_DEFAULT`) como fallback para
o seed inicial do banco. Os defaults são usados pelo `parametros_default.json`
e pelo `ParametroRepository` quando uma chave não existe no banco.

## Contrato (Requisitos)

### `ParametroOperacional(chave, valor, estrategia, descricao, ...)`

**Garante:**
1. `chave: str` — chave única de identificação (ex: `"taxa_cdi"`).
2. `valor: float` — valor do parâmetro. **POSSÍVEL BUG:** a anotação é `float`,
   mas várias chaves armazenam strings (ex: `"fonte_market_data"`, `"som_arquivo"`,
   `"put_ratio_ratios"`, `"bwb_modo"`, `"white_list_box4p"`). O tipo real
   aceito em runtime é `str | float`.
3. `estrategia: str` — categoria da estratégia (ex: `"BOX"`, `"SBTH"`, `"GERAL"`,
   `"COLLAR_CALENDARIO"`, `"MPP"`). Usado para agrupamento na UI e filtros.
4. `descricao: str` — descrição legível para exibição na tabela de parâmetros.
5. `id: int | None` — populado pelo repositório após INSERT.

### `defaults()` (classmethod)

**Garante:**
1. Retorna `list[ParametroOperacional]` com todos os parâmetros definidos em
   `PARAMETROS_DEFAULT`.
2. Cada item é instanciado como `cls(chave=k, valor=v["valor"], estrategia=v["estrategia"], descricao=v["descricao"])`.
3. A ordem segue a ordem de definição do dict (Python 3.7+ garante ordem de inserção).

### `PARAMETROS_DEFAULT` (class-level dict)

**Garante:**
1. Contém ~160 parâmetros organizados por estratégia.
2. Cada entrada tem `{"valor": ..., "estrategia": ..., "descricao": ...}`.
3. É a fonte de verdade para o seed inicial do banco (junto com `config/parametros_default.json`).
4. Inclui parâmetros para: GERAL, BOX, SBTH, BOX_SINTETICO, COLAR, COLLAR_CALENDARIO,
   MPP, VENDA_COBERTA, VENDIDAS, SBTH_VENDIDA, TAXA_COMPRADA, PROTECAO_CAUDA,
   PUT_RATIO, RATIOS_OTIMIZADOS, TELEGRAM, SOM, PERFORMANCE, IMPORTACAO.
5. O valor default de `fonte_market_data` hardcoded aqui é `"profit"`, mas o
   `parametros_default.json` tem `"openfast"` — o JSON vence no seed (documentado
   no AGENTS.md).

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `dataclasses` | `dataclass` | Decorador da classe |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 204 |
| Classes | 1 |
| Métodos/Funções | 1 classmethod (`defaults`) |
| Complexidade ciclomática estimada | Baixa |
| Testes | Parcial (indireto via `ParametroRepository` e fixtures de seed) |

## Notas

- [2026-05-11 via git log] módulo criado. Última modificação: 2026-08-07 (atualização
  frequente — parâmetros adicionados conforme novas estratégias).
- **POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão:** o campo `valor` é anotado
  como `float`, mas diversas chaves armazenam strings:
  - `"fonte_market_data"`: `"profit"` (string)
  - `"som_arquivo"`, `"som_arquivo_vendidas"`, `"som_arquivo_coberta"`: `""` (string vazia)
  - `"telegram_bot_token"`, `"telegram_chat_id"`: `"0"` (string)
  - `"put_ratio_ratios"`: `"1x2,2x3,1x3"` (string)
  - `"bwb_modo"`: `"simples"` (string)
  - `"white_list_box4p"`, `"white_list_colar_calendario"`, `"white_list_colar"`,
    `"white_list_put_ratio"`, `"black_list_box4p"`, `"black_list_import"`: `""` (string vazia)
  
  Isso faz com que `ParametroRepository.get_by_chave()` retorne `float` para
  a maioria das chaves, mas `str` para estas. O código consumidor precisa
  fazer coerção ou `isinstance` check. A anotação `valor: float` é inconsistente
  com a realidade dos dados.
- **POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão:** o default hardcoded de
  `fonte_market_data` é `"profit"` no `PARAMETROS_DEFAULT`, mas `"openfast"` no
  `parametros_default.json`. Isso está documentado no AGENTS.md como "o JSON
  vence no seed", mas a discrepância é uma armadilha para manutenção — se alguém
  mudar o seed sem atualizar o JSON, o comportamento padrão muda silenciosamente.
- O `PARAMETROS_DEFAULT` funciona como fallback para o `ParametroRepository`: se
  uma chave não existe no banco, o repositório retorna o valor do dict de defaults.
- Regra #3 do AGENTS.md: ao adicionar um novo parâmetro, é obrigatório tocar em
  4 arquivos: este (`parametro_operacional.py`), `config/parametros_default.json`,
  `parametros_widget.py` e `regras_dialog.py`.
