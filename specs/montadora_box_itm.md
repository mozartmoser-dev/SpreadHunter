# MontadoraBoxItm

## Propósito

Montadora de estruturas BOX ITM (In-The-Money) — o serviço que transforma candidatos
elegíveis de pescaria em cestas (`BoxItmBasket`) de 3 pernas operacionais prontas para
exportação ou execução. A estrutura consiste em: compra da CALL ITM (deep ITM, substituta
do ativo), compra da PUT ATM (proteção) e venda da CALL ATM (financiamento).

**Papel real no sistema (descoberto via grep, 07/08/2026):** o `MontadoraBoxItm` é
instanciado pelo use case `ExportarOperacaoUseCase` (`exportar_operacao.py:25`) com
`profundidade_call_itm=-1`, e usado para montar baskets a partir de candidatos filtrados.
É um serviço de domínio com estado mínimo (`profundidade_call_itm` no construtor) e
dois comportamentos: montagem de pernas + cálculo de coeficientes de viabilidade.

`BoxItmBasket` é um dataclass de transporte que encapsula o resultado da montagem:
tipo da estrutura, lista de pernas, coeficientes alvo/mercado e taxa de ganho.

## Contrato (Requisitos)

### `__init__(profundidade_call_itm: int = -1)`

**Garante:**
1. `profundidade_call_itm` é o offset de profundidade da CALL ITM na cadeia de strikes.
   Default `-1` = primeiro strike abaixo do ATM. Usado via `PernaOperacao.profundidade`
   nas pernas montadas.
2. O valor é armazenado como atributo de instância e aplicado a todas as baskets montadas
   por esta instância.

### `montar_3_pernas(cod_call_itm, cod_put_atm, cod_call_atm, estrutura_id, coefic_alvo=0.0, coefic_mercado=0.0, taxa_ganho=0.0) -> BoxItmBasket`

**Garante:**
1. Cria exatamente 3 pernas na ordem:
   - **Perna 1** (ordem=1): COMPRA da CALL ITM, `quantidade=100`, `profundidade=self.profundidade_call_itm`
   - **Perna 2** (ordem=2): COMPRA da PUT ATM, `quantidade=100`, `profundidade=0`
   - **Perna 3** (ordem=3): VENDA da CALL ATM, `quantidade=100`, `profundidade=0`
2. Todas as pernas compartilham o mesmo `estrutura_id`.
3. `quantidade` é sempre 100 (lote padrão B3) — hardcoded, não parametrizável.
4. Retorna `BoxItmBasket` com `tipo=TipoEstrutura.BOX_ITM_BASKET`.
5. Os códigos de opção (`cod_call_itm`, `cod_put_atm`, `cod_call_atm`) são aceitos
   como strings sem validação de formato — a validação é responsabilidade do chamador.

### `calcular_coeficientes(strike_atm, strike_itm, premio_call_atm, premio_call_itm, premio_put_atm, taxa_ganho=0.0) -> tuple[float, float]`

**Garante:**
1. Retorna `(coefic_alvo, coefic_mercado)` como frações do spread ATM-ITM.
2. `spread = strike_atm - strike_itm`. Se `spread <= 0`, retorna `(0.0, 0.0)`.
3. `custo_estrutura = premio_call_itm + premio_put_atm - premio_call_atm`.
   - Compra CALL ITM (+ prêmio pago), compra PUT ATM (+ prêmio pago), vende CALL ATM (− prêmio recebido).
   - Custo positivo = estrutura tem débito (paga-se para montar).
4. `coefic_alvo = (100.0 - taxa_ganho) / 100.0` se `taxa_ganho >= 0`; senão `1.0`.
   - Ex: `taxa_ganho=10` → `coefic_alvo=0.90` (máximo 90% do spread pode ser gasto).
5. `coefic_mercado = custo_estrutura / spread` se `spread != 0`.
6. Ambos os coeficientes são arredondados para 4 casas decimais.
7. **Operação é viável quando `coefic_mercado <= coefic_alvo`** — o custo real como
   fração do spread é menor ou igual ao máximo aceitável. Esta verificação é feita
   pelo chamador (use case), não pela montadora.

## Decisões Tomadas

### 1. `profundidade_call_itm` como atributo de instância (não parâmetro por chamada)

**Porquê:** A profundidade é uma configuração global da estratégia (definida uma vez
no `ExportarOperacaoUseCase`), não varia entre baskets. Passar como atributo de instância
evita repetição do parâmetro em cada chamada de `montar_3_pernas()`.

### 2. `quantidade=100` hardcoded

**Porquê:** O lote padrão B3 para opções sobre ações é 100. Não há cenário de produção
onde a quantidade seja diferente. Hardcodar evita o risco de o chamador passar uma
quantidade inválida. Se no futuro houver necessidade de lotes fracionados ou múltiplos,
basta adicionar o parâmetro.

### 3. Ordem fixa das pernas (1=ITM, 2=PUT, 3=CALL)

**Porquê:** A ordem das pernas é relevante para exibição na UI e para o motor de
execução (a perna 1 é a âncora da estrutura). Fixar a ordem na montadora garante
consistência entre todas as baskets geradas.

### 4. `coefic_alvo` derivado de `taxa_ganho` com fórmula `(100 - taxa) / 100`

**Porquê:** A taxa de ganho é expressa como percentual (ex: 10 = 10% de retorno sobre
o spread). O coeficiente alvo é o complemento: se quero 10% de ganho, posso gastar
até 90% do spread. Esta convenção é consistente com outras calculadoras do sistema
(`calculadora_box.py`, `calculadora_box_sbth.py`).

### 5. `calcular_coeficientes()` retorna tupla em vez de `BoxItmBasket`

**Porquê:** O cálculo de coeficientes é uma operação de pré-viabilidade que acontece
antes da montagem das pernas. O chamador primeiro verifica se `coefic_mercado <=
coefic_alvo` e só então chama `montar_3_pernas()`. Separar as operações evita
criar `PernaOperacao` e `BoxItmBasket` para candidatos inviáveis.

## Decisões Rejeitadas

### 1. `montar_3_pernas()` aceitar `quantidade` como parâmetro

Rejeitado porque o lote padrão é sempre 100. Adicionar o parâmetro sem necessidade
real aumentaria a superfície de erro (chamador passar quantidade errada).

### 2. `calcular_coeficientes()` integrado em `montar_3_pernas()`

Rejeitado para separar verificação de viabilidade (barata, só floats) de montagem
de objetos (cria entidades, aloca listas). O chamador pode filtrar dezenas de
candidatos calculando coeficientes e só montar pernas para os viáveis.

### 3. `profundidade_call_itm` como constante de módulo

Rejeitado porque diferentes instâncias podem precisar de profundidades diferentes
(ex: testes vs produção, ou diferentes estratégias). Atributo de instância é mais
flexível e não custa nada (a classe é instanciada uma vez por uso).

## Dependências

- `dataclasses` — stdlib
- `src.domain.entities.estrutura_operacional` → `TipoEstrutura`
- `src.domain.entities.perna_operacao` → `PernaOperacao`, `Lado`

**Não depende de:**
- Banco de dados, repositórios, parâmetros operacionais
- RTD/OpenFAST
- `ElegibilidadePescaria` (é complementar, mas independente — a montadora recebe
  candidatos já filtrados, não chama o filtro)

**É dependência de:**
- `src/application/use_cases/exportar_operacao.py` (`ExportarOperacaoUseCase`)
- `tests/test_fase2.py` (`TestMontadoraBoxItm`)

## Cobertura de Teste

**Status: 2 testes em `tests/test_fase2.py`** (classe `TestMontadoraBoxItm`)

| Teste | Cobre |
|---|---|
| `test_montar_3_pernas` | Montagem de basket: 3 pernas, tipo, códigos, lados, profundidades, ordens |
| `test_calcular_coeficientes` | Cálculo: `strike_atm=18`, `strike_itm=10`, spread=8, custo=7.5, `coefic_mercado=0.9375` |

**Lacunas conhecidas (não cobertas):**
- `montar_3_pernas()` com `profundidade_call_itm` diferente de -1 — 0 testes
- `calcular_coeficientes()` com `spread <= 0` — 0 testes
- `calcular_coeficientes()` com `taxa_ganho < 0` (fallback `coefic_alvo=1.0`) — 0 testes
- `calcular_coeficientes()` com `premio_call_atm > premio_call_itm + premio_put_atm`
  (custo negativo = crédito) — 0 testes
- Integração com `ExportarOperacaoUseCase` — 0 testes de integração
