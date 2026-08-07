# MarketAnalyzer

## Propósito

Classificador de momento de mercado em tempo real. Analisa a variação da curva de DI futuro
(DI1F33 vs DI1F27) para determinar regime de estresse/alívio no mercado de juros e classifica
o vetor macroeconômico (RISK-ON, RISK-OFF, COMMODITIES, DEFENSIVO, MISTO) com base nas
variações de WDO, WIN, DI1F33, Brent e SGX.

**Papel real no sistema (descoberto via grep, 07/08/2026):** o `MarketAnalyzer` é um serviço
de domínio sem estado — todos os métodos são `@staticmethod`. É consumido exclusivamente pelo
widget de UI `sensibilidade_mercado_widget.py`, que monta o dashboard "Market Sensitivity"
na interface principal. O serviço é puramente reativo: recebe variações percentuais/pontos
já calculadas pelo widget (que busca cotações de `FieldName` via RTD/OpenFAST) e retorna
cores, ícones e classificações para renderização.

`AnaliseMercadoResult` é um dataclass auxiliar (não usado no código atual — o retorno de
`processar_tick()` é um `dict` simples, não uma instância de `AnaliseMercadoResult`).
POSSÍVEL BUG — a dataclass foi criada como contrato de resultado mas `processar_tick()` e
os outros métodos nunca a instanciam; o widget espera `dict`. Código morto ou refatoração
incompleta, aguardando revisão.

## Contrato (Requisitos)

### `analisar_curva_di(di1f33_var_pontos: float) -> tuple[str, str, str]`

**Garante:**
1. Se `di1f33_var_pontos > 0` (abertura da curva = estresse): retorna `("STRESS", "↑", "#e74c3c")`.
2. Caso contrário (fechamento = alívio): retorna `("ALÍVIO", "↓", "#2ecc71")`.
3. Não há estado neutro/zero — `<= 0` sempre é ALÍVIO, mesmo com variação zero.

### `analisar_vetor(win_var, wdo_var, di1f33_var_pontos, brent_var=0.0, sgx_var=0.0) -> str`

**Garante:**
1. RISK-ON: `win_var > 0 AND wdo_var < 0 AND di1f33_var_pontos < 0` (bolsa sobe, dólar cai, juro cai).
2. RISK-OFF: `win_var < 0 AND wdo_var > 0 AND di1f33_var_pontos > 0` (bolsa cai, dólar sobe, juro sobe).
3. COMMODITIES: `win_var > 0 AND di1f33_var_pontos > 0 AND brent_var > 0 AND sgx_var > 0`.
4. DEFENSIVO: `wdo_var > 0 AND di1f33_var_pontos > 0` (dólar e juro sobem juntos).
5. MISTO: fallback quando nenhum dos padrões acima é satisfeito.
6. A ordem de avaliação importa: RISK-ON e RISK-OFF são testados primeiro, depois COMMODITIES,
   depois DEFENSIVO. Se um tick satisfaz múltiplos padrões, vence o primeiro na ordem.

### `vetor_cor(vetor: str) -> str`

**Garante:**
1. Mapeia cada vetor para uma cor hex: RISK-ON → `#2ecc71` (verde), RISK-OFF → `#e74c3c`
   (vermelho), COMMODITIES → `#f0c040` (amarelo), DEFENSIVO → `#e67e22` (laranja),
   MISTO → `#9090b0` (cinza-azulado).
2. Fallback para `#9090b0` para qualquer string não reconhecida (via `.get(vetor, ...)`).

### `cor_heatmap(var: float) -> str`

**Garante:**
1. Faixas discretas de cor baseadas na variação percentual:
   - `var <= -1.5` → `#e74c3c` (queda forte, vermelho intenso)
   - `-1.5 < var < 0` → `#c0392b` (queda moderada, vermelho escuro)
   - `var == 0` → `#606080` (neutro, cinza)
   - `0 < var < 1.5` → `#27ae60` (alta moderada, verde escuro)
   - `var >= 1.5` → `#2ecc71` (alta forte, verde intenso)
2. Igualdade exata com zero (`var == 0`): comparação float sem tolerância — POSSÍVEL BUG,
   variações muito pequenas (ex: `1e-10`) são tratadas como `var < 1.5` (verde) em vez de
   neutro (cinza). Em ticks reais isso raramente ocorre porque as variações vêm já
   arredondadas do `processar_tick()`.

### `icone_heatmap(var: float) -> str`

**Garante:**
1. Ícones Unicode para as mesmas faixas de `cor_heatmap`:
   - `<= -1.5` → `"▼"`, `< 0` → `"▽"`, `== 0` → `"—"`, `< 1.5` → `"△"`, `>= 1.5` → `"▲"`.
2. Mesma lógica de igualdade float que `cor_heatmap()`.

### `deve_emitir(cod: str) -> bool`

**Garante:**
1. Retorna `True` para qualquer código — a função sempre retorna `True`.
2. POSSÍVEL BUG — código morto: os branches `DI1F27` e `DI1F33` eram provavelmente
   uma whitelist que foi desabilitada ao fazer todos os caminhos retornarem `True`.
   A função é chamada por `processar_tick()` como guard clause, mas nunca filtra nada.
   Se a intenção original era filtrar por código, o comportamento atual é um bug;
   se a intenção era sempre emitir, a função é redundante e os branches `DI1F27`/`DI1F33`
   são código morto. Aguardando revisão.

### `processar_tick(codigo, preco, ref_prices, ref_settled) -> dict`

**Garante:**
1. Se `deve_emitir(codigo)` retorna `False`, retorna `{"var": 0.0, "var_str": "", "cor": "#888"}`.
   (Na prática, nunca acontece — `deve_emitir` sempre retorna `True`.)
2. No primeiro tick com `preco > 0` de cada código: registra `ref_prices[codigo] = preco`
   como preço de referência e marca `ref_settled.add(codigo)`.
3. `ref_prices` e `ref_settled` são mutados in-place (side effect) — a função é impura.
4. Cálculo da variação: `((preco - ref) / ref * 100)` se `ref > 0`.
5. Se `preco > 0`, formata `var_str` com sinal e 2 casas decimais; se `abs(var) >= 1.5`,
   prefixa com ícone do `icone_heatmap()`.
6. Se `preco <= 0`, retorna `var_str = ""` (vazio).
7. Retorna `dict` (não `AnaliseMercadoResult`) com chaves `var`, `var_str`, `cor`.

## Decisões Tomadas

### 1. Serviço sem estado (todos métodos `@staticmethod`)

**Porquê:** O `MarketAnalyzer` não mantém estado entre chamadas — cada tick é processado
isoladamente. O estado (preços de referência) é mantido externamente pelo widget chamador
(`sensibilidade_mercado_widget.py`), que passa `ref_prices` e `ref_settled` como argumentos
mutáveis. Isso separa a lógica de classificação (domínio puro) do gerenciamento de estado
(UI), facilitando testes unitários.

**Trade-off:** O contrato de `processar_tick()` é confuso porque o método é formalmente
`@classmethod` mas muta seus argumentos `ref_prices` e `ref_settled`. Seria mais claro
como função pura retornando o novo estado, mas o design atual evita alocações extras.

### 2. Ordem de precedência fixa no `analisar_vetor()`

**Porquê:** RISK-ON e RISK-OFF são padrões mais fortes e específicos (3 condições cada).
COMMODITIES e DEFENSIVO são padrões mais fracos. Avaliar os padrões fortes primeiro evita
que um tick que é claramente RISK-ON seja classificado como COMMODITIES se também satisfizer
esse padrão.

### 3. Cores e ícones definidos como constantes inline (não extraídos para enum/config)

**Porquê:** As cores são parte da identidade visual do dashboard e mudam raramente.
Extrair para configuração do banco adicionaria indireção sem ganho real — o widget já
aplica as cores diretamente no QPainter/QBrush.

### 4. `deve_emitir()` sempre retorna `True`

**Porquê:** [motivo não documentado, confirmar com o autor]. A função parece ter sido
projetada como whitelist de códigos monitorados (DI1F27, DI1F33) mas foi neutralizada
ao fazer todos os branches retornarem `True`. Possivelmente durante o desenvolvimento
do dashboard decidiu-se que todos os ticks de todos os ativos deveriam ser processados,
mas a guard clause não foi removida para manter compatibilidade.

### 5. `processar_tick()` retorna `dict` em vez de `AnaliseMercadoResult`

POSSÍVEL BUG — a dataclass `AnaliseMercadoResult` existe no módulo com campos
(`curva_status`, `curva_seta`, `curva_cor`, `vetor`, `vetor_cor`) que correspondem a
um resultado agregado de análise, mas `processar_tick()` retorna um `dict` simples
(`var`, `var_str`, `cor`) que é usado pelo widget. A dataclass nunca é instanciada
em produção — possível refatoração incompleta ou contrato planejado não implementado.
Aguardando revisão.

## Decisões Rejeitadas

### 1. Extrair faixas de heatmap para parâmetros do banco

Rejeitado porque os thresholds (`-1.5`, `0`, `1.5`) são convenções visuais fixas,
não parâmetros de negócio. Mudanças nesses valores alterariam a semântica das cores
no dashboard de forma inconsistente com a expectativa do usuário.

### 2. Usar `Enum` para vetores de mercado

Rejeitado porque o método já retorna strings e o consumidor (`sensibilidade_mercado_widget.py`)
faz comparações diretas de string. Adicionar um `Enum` exigiria refatoração do widget
sem ganho de type safety (as strings são usadas como chaves de dicionário no `vetor_cor()`).

### 3. `processar_tick()` como função pura (retornando novo estado)

Rejeitado porque `ref_prices` e `ref_settled` são shared mutable state entre múltiplos
códigos no widget. Retornar cópias a cada tick alocaria dicionários desnecessariamente
em um loop de alta frequência (múltiplos ticks por segundo durante o mercado).

## Dependências

- `logging`, `dataclasses` — stdlib
- **Não depende de:** entidades de domínio, repositórios, RTD/OpenFAST, banco de dados

**É dependência de:**
- `src/ui/desktop/sensibilidade_mercado_widget.py` (único consumidor em produção)

## Cobertura de Teste

**Status: 0 testes.**

O módulo não possui testes unitários diretos. É exercitado indiretamente via
`sensibilidade_mercado_widget.py` durante execução do dashboard, mas não há
cobertura automatizada.

**Lacunas conhecidas (não cobertas):**
- `analisar_curva_di()` com valor zero — 0 testes
- `analisar_vetor()` com todas as combinações de vetores — 0 testes
- `analisar_vetor()` com `brent_var` e `sgx_var` padrão (0.0) vs valores reais — 0 testes
- `cor_heatmap()` e `icone_heatmap()` em valores de borda — 0 testes
- `processar_tick()` com `ref_prices` vazio vs populado — 0 testes
- `processar_tick()` com `preco <= 0` — 0 testes
- Comportamento de `deve_emitir()` retornando sempre `True` — 0 testes
- `AnaliseMercadoResult` dataclass — 0 usos, 0 testes
