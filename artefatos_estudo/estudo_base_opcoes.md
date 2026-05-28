# Especificações Técnicas: Projeto Spreadhunter (B3 Options)

## 1. Infraestrutura de Dados (Data Sourcing)

### 1.1. Extração via Scrapy/Requests (Prioridade Técnica)
- **Alvo:** `opcoes.net.br`
- **Método:** Inspecionar e replicar chamadas AJAX (JSON) para evitar o overhead do Playwright.
- **Headers:** Mimetizar `User-Agent` de navegadores modernos e utilizar `session` para manter cookies, contornando WAFs simples.
- **Dados Necessários:** Ticker, Tipo (Call/Put), Strike, Vencimento, Modelo (A/E), Vol. Implícita e Gregas.

---

## 2. Engenharia Financeira e Matemática (Padrão B3)

### 2.1. Convenção de Tempo e Taxas
A B3 opera sob a convenção de **Dias Úteis (DU/252)**. O uso de dias corridos (365) **INVALIDA** os cálculos de arbitragem e precificação de Gregas.

- **Tempo (T):** Deve ser calculado como $T = DU / 252$ para Black-Scholes e Gregas.
- **Calendário:** Utilizar `numpy.busday_count` alimentado por uma lista oficial de feriados da ANBIMA/B3.
- **Dias Corridos (DC/365):** Utilizar apenas para exibição em interface (UI) e contagem regressiva linear.
- **Taxa de Juros (r):** Utilizar a Taxa DI (SELIC). A capitalização é composta: $Fator = (1 + r)^{DU/252}$.
  - *Nota:* Em feriados, o "tempo para" para o CDI e para o decaimento (Theta) das opções.
- **Volatilidade (sigma):** Deve ser anualizada sobre 252 dias. Se o dado vier em base 365, deve ser normalizado antes de entrar no modelo.

### 2.2. Modelo de Precificação
- **Calls:** Majoritariamente **Americanas** (podem ser exercidas antes do vencimento). O modelo de Black-Scholes pode subestimar o preço; considerar modelos binomiais se houver proximidade de dividendos.
- **Puts:** Majoritariamente **Europeias** (exercício apenas no vencimento).

---

## 3. Lógica das Calculadoras (Estratégias)

### 3.1. Calculadora Box SBTH (Arbitragem de 4 Pontas)
- **Objetivo:** Montar uma estrutura sintética de renda fixa.
- **Equação:** $+Call_{K1} -Call_{K2} -Put_{K1} +Put_{K2}$.
- **Requisito Técnico:** Calcular o Valor Presente (VP) do Spread de Strikes $(K2 - K1)$ descontado pela taxa DI no período DU.
- **Custo de Fricção:** Deve subtrair taxas de corretagem e a tabela de emolumentos da B3 por perna executada.
- **Risco não coberto:** Exercício antecipado da perna Call vendida em caso de forte alta e proventos.

### 3.2. Calculadora Colar e Colar Calendário
- **Colar Simples:** Compra do Ativo + Compra de Put (ATM/OTM) + Venda de Call (OTM).
- **Otimização:** Busca iterativa pelo "Zero Cost Collar" (onde Prêmio Recebido Call $\approx$ Prêmio Pago Put + Taxas).
- **Calendário:** Exposição ao *Skew* de volatilidade entre vencimentos. A calculadora deve alertar sobre o diferencial de Theta entre a ponta curta e a ponta longa.

---

## 4. Arquitetura do Software (Python)

### 4.1. Módulos Core
1. `finance_math.py`: Centraliza conversões de tempo (DU vs DC) e cálculos de Black-Scholes adaptados para 252 dias.
2. `data_provider.py`: Gerencia o scraping/AJAX e normalização dos dados recebidos.
3. `calculators/`: Um arquivo por estratégia, herdando premissas de juros e tempo do `finance_math.py`.

### 4.2. Tratamento de Erros e Slippage
- Implementar um "Buffer de Execução": considerar sempre o preço de *Ask* para compras e *Bid* para vendas no cálculo de viabilidade, simulando a realidade do book de ofertas.

---

## 5. Resumo de Riscos para Implementação
1. **Liquidez:** Spreads largos na B3 podem invalidar a arbitragem teórica.
2. **Taxas B3:** Emolumentos são regressivos, mas pesados para operações multi-leg.
3. **Temporalidade:** O descasamento entre dias úteis e corridos gera erro de 31% na base de cálculo se não for tratado adequadamente.

---

## 6. Diretrizes de Codificação para a Próxima Fase
1. **Modularidade**: Mantenha o motor de cálculo (`finance_math.py`) isolado da lógica de scraping.
2. **Type Hinting**: Utilize tipagem estrita para evitar confusão entre `float` (taxas) e `int` (dias úteis).
3. **Fórmulas de Juros**: 
   - Sempre use: `Fator = (1 + taxa_di) ** (du / 252)`. 
   - **NUNCA** utilize `e^(rt)` para produtos baseados em DI na B3.
4. **Modelo de Opções**:
   - Para PUTs: Black-Scholes é aceitável (europeias).
   - Para CALLs: Se o ativo-objeto estiver próximo de pagar dividendos, prefira o modelo Binomial (Cox-Ross-Rubinstein) devido à natureza americana das opções.
5. **Slippage**: Em estratégias multileg (Box/Collar), assuma sempre que a execução ocorre no pior lado do book (Ask para compra, Bid para venda).

---

## 7. Roadmap de Implementação (Gemini Finalized)
Para sair do rascunho e chegar ao sistema funcional, siga esta ordem:

1.  **Fase 1 (Core)**: Validar `finance_math.py` com o calendário ANBIMA atualizado.
2.  **Fase 2 (Ingestão)**: Implementar `data_provider.py` usando `httpx` para chamadas JSON ao `opcoes.net.br`, extraindo strikes e volatilidade implícita.
3.  **Fase 3 (Scanner Box SBTH)**: Criar script que filtra opções Europeias, calcula o Valor Presente do Spread e identifica retornos acima de 105% do CDI, descontando emolumentos.
4.  **Fase 4 (Scanner Collar)**: Implementar busca iterativa por Strikes de custo zero para PETR4 e VALE3, priorizando Puts com Delta entre -30 e -40.
5.  **Fase 5 (Execução)**: Formatar o output final para o formato de importação do PNT (Plug and Trade).
