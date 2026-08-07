# ClassificacaoOportunidade

Regras de classificação de oportunidades — converte o resultado da calculadora
BOX/SBTH (`ResultadoBOXSBTH.classificacao`) em enum de domínio (`ClassificacaoOp`)
e determina qual operação é viável com base em ganho positivo.

## Contrato (Requisitos)

### `classificar(resultado: ResultadoBOXSBTH) -> ClassificacaoOp`
**Garante:**
1. Mapeia strings da calculadora → enum:
   - `"1BOX"` → `ClassificacaoOp.BOX_1`
   - `"2SBTH"` → `ClassificacaoOp.SBTH_2`
   - `"3BOXSBTH"` → `ClassificacaoOp.BOXSBTH_3`
   - `"TP.Op"` → `ClassificacaoOp.TP_OP`
2. Fallback: qualquer string não mapeada → `ClassificacaoOp.TP_OP`.
3. Método estático — stateless.

### `determinar_operacao_viavel(oportunidade: Oportunidade) -> str`
**Garante:**
1. Retorna `"BOX"` se `classificacao == BOX_1` e `pct_ganho_box > 0`.
2. Retorna `"SBTH"` se `classificacao == SBTH_2` e `pct_ganho_sbth > 0`.
3. Retorna `"BOXSBTH"` se `classificacao == BOXSBTH_3` e **ambos** `pct_ganho_box > 0` e `pct_ganho_sbth > 0`.

   **BUG CONFIRMADO (2026-08-07):** Se apenas um lado for positivo em BOXSBTH_3,
   retorna `"NEUTRA"` em vez de `"BOX"` ou `"SBTH"`. Este método é **código espelho**
   de `calculadora_box_sbth._determinar_operacao()` e **não é chamado em produção**
   — apenas nos testes de `test_fase2.py`. O bug real foi corrigido na calculadora
   (`calculadora_box_sbth.py:162-168`), que é o código executado pelo
   `MonitorOportunidadesUseCase`. Ver `specs/calculadora_box_sbth.md` para o fix
   e cenário de regressão. Este espelho permanece não corrigido por não ter
   impacto em produção.
4. `ClassificacaoOp.TP_OP` → `"TP"`.
5. Qualquer outra → `"NEUTRA"`.

### `filtrar_viaveis(oportunidades: list[Oportunidade]) -> list[Oportunidade]`
**Garante:**
1. Filtra apenas oportunidades com `operacao in ("BOX", "SBTH", "BOXSBTH")`.
2. Método estático puro.

### `filtrar_por_liquidez(oportunidades, min_liq_put=0, min_liq_call=0) -> list[Oportunidade]`
**Garante:**
1. Filtra `liq_put_x_lote >= min_liq_put` e `liq_call_x_lote >= min_liq_call`.
2. Defaults `0` — sem filtro se não especificado.

### `filtrar_sem_leilao(oportunidades: list[Oportunidade]) -> list[Oportunidade]`
**Garante:**
1. Remove oportunidades com `em_leilao == True`.
2. Filtro binário simples.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| src.domain.entities.oportunidade | `ClassificacaoOp`, `Oportunidade` | Enum + entidade |
| src.domain.services.calculadora_box_sbth | `ResultadoBOXSBTH` | Entrada do `classificar()` |

**É dependência de:**
- `tests/test_fase2.py` — 3+ testes (classificação, viavel, sem_leilao)

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 41 |
| Arquivo | `src/domain/rules/classificacao_oportunidade.py` |
| Última modificação | 2026-05-11 |

## Notas
- 2026-05-11: arquivo criado (apenas 1 commit — código estável desde a criação).
- Todos os métodos são `@staticmethod` — a classe é um namespace, não um serviço com estado.
- Testes em `test_fase2.py` (classe `TestClassificacaoOportunidade`).
- POSSÍVEL BUG em `determinar_operacao_viavel` com BOXSBTH_3 de um lado só (ver acima).
