# Pendências — Colar Calendário / BWB

## Diagnóstico: BWB sempre `nenhum`

### Filtro 1: `cab` no `_coletar_lado` (`monitor_worker.py:1189`)
- **Causa:** `cab = vol_ask`. OpenFAST entrega `vol_ask=0` para calls OTM profundas, mas `vol_bid` tem valor (ex: BBASH260 K=23.90, va=0 vb=503800).
- **Relaxação atual:** `if vol_ask <= 0 and vol_bid <= 0` — só ativa quando AMBOS zerados. Não cobre o caso `va=0, vb>0`.
- **Efeito:** 95%+ das calls que passam direção são descartadas com `cab=0 < min=1`.
- **Possível correção:** `cab = max(vol_ask, vol_bid)` no OpenFAST.

### Filtro 2: liquidez no `_avaliar_lado` (`calculadora_protecao_cauda.py:177`)
- **Causa:** `min(vol_ask, vol_bid) >= limite_liquidez`. Se `vol_ask=0`, `min(0, X)=0` → barrado de novo.
- **Mesma raiz do Filtro 1:** OpenFAST não entrega VOL_ASK para OTM.
- **Possível correção:** usar `max(vol_ask, vol_bid)` em vez de `min`.

### Filtro 3: custo no `_avaliar_lado` (`calculadora_protecao_cauda.py:223`)
- **Causa:** `custo <= ganho_extra_ratio * limite_protecao_pct`. Com `limite_protecao_pct=0.99%` no banco.
- **Exemplo real (BBAS3):** ganho_extra=R$370, orçamento=R$3.66, call custa R$780.
- **Usuário quer 30%.** Plan (`planoprotecaocauda.md`) sugere default 35%.
- Mesmo a 100% (R$370), call de R$780 não passaria.

### Filtro 4: distância do strike-alvo
- **Causa:** `n_sigma=2.0` joga `s_target` muito longe. Calls a 2σ têm prêmio elevado (vega/skew).
- **Consequência:** mesmo corrigindo cab + custo, calls podem ser caras demais para o ganho extra disponível.

## Correção de conceito: BWB

- **BWB (Broken Wing Butterfly)** = butterfly com asas assimétricas. Corpo (2 vendidas no meio) financia as asas (1 comprada em cada ponta). Estrutura creditícia ou custo quase zero.
- **Erro anterior:** tratada como compra de proteção pura (débito), quando deveria ser autofinanciada pelo prêmio das vendas do corpo (short call do collar).
- **Próximo passo:** redesenhar lógica de seleção para buscar strike onde custo ≤ ganho extra, em vez de fixar 2σ.

## Simulação Real: PETR4 (Rendimento 1.30x) — 21/07/2026 11:57

### Dados base
| Campo | Valor |
|-------|-------|
| Preço | R$ 41.63 |
| Short call | PETRH424 K=41.36 ASK=1.81 DTE=31 |
| Long put | PETRV42 K=41.38 BID=2.21 DTE=87 |
| σ período | ~21.5% |
| Crédito líquido | 1.3 × 1.81 − 1.0 × 2.21 = R$ 0.14/share |
| Breakeven | 41.36 + 0.14/1.3 = **R$ 41.47** |
| Qtd ações | ~1000 (Custo R$ 42.030) |
| Calls nuas | 300 shares (0.30 × 1000) |
| Ganho extra | R$ 1.650 − R$ 1.188 = **R$ 462** |

### Descoberta: alvo é breakeven, não 2σ
A BWB deve ser montada no **breakeven** (onde o prejuízo começa), não em 2σ.
Para PETR4, breakeven = R$ 41.47 — apenas 16 centavos acima do preço.
Isso faz as calls do corpo estarem quase ATM (caras), dificultando a borboleta.

### Prêmios reais (OpenFAST OCP, PETRH421 DTE 31)
```
K=41.61: 1.67 | K=43.11: 1.00 | K=44.11: 0.69 | K=45.36: 0.43
K=46.61: 0.27 | K=47.61: 0.19 | K=48.11: 0.15 | K=50.61: 0.07
K=51.11: 0.06 | K=51.61: 0.05 | K=52.11: 0.04 | K=55.11: 0.02
K=56.61: 0.01 | K=57.11: 0.01
```

### Butterfly simulada (K≈50, 300 shares)
```
VENDE 6 × K=50.61 (PETRH517) @ 0.07 = +R$ 42
COMPRA 3 × K=47.61 (PETRH487) @ 0.19 = −R$ 57
COMPRA 3 × K=55.11 (PETRH562) @ 0.02 = −R$ 6
                              Líquido = −R$ 21
```
Custo: R$ 21 = **4.5%** do ganho extra (R$ 462).
PnL base collar: R$ 1.188 mantido. PnL pós-BWB: R$ 1.506 (+27% vs base).

### Butterfly no breakeven (K≈43, 300 shares)
```
VENDE 6 × K=43.11 (PETRH500) @ 1.00 = +R$ 600
COMPRA 3 × K=41.61 (PETRH427) @ 1.67 = −R$ 501
COMPRA 3 × K=46.61 (PETRH477) @ 0.27 = −R$ 81
                              Líquido = +R$ 18 (crédito teórico)
```
Na prática spread BID/ASK come o crédito (asa inf quase ATM).

### Conclusões da simulação
1. **BWB é viável** com dados reais — custo de 4.5% a 31% do ganho extra
2. **Depende do collar**: breakeven perto do preço → asa inf cara → BWB menos eficiente
3. **Collares com breakeven distante** (ex: VALE3 com crédito folgado) teriam BWB mais barata
4. **40% do ganho extra** como teto é factível, deixando folga para convexidade (lotto ticket)
5. O custo do BWB consome só o ganho extra do ratio — o PnL base fica intocado
6. Ratio na put < 1.0 também gera nu no downside — BWB precisaria cobrir os dois lados

### Redesenho necessário
- Alvo do BWB = **breakeven da estrutura com ratio**, não 2σ fixo
- Buscar strike do corpo mais próximo acima do breakeven com liquidez
- Asa inferior e superior definidas pelos strikes disponíveis com menor custo líquido
- Se custo > 40% do ganho extra → BWB inviável para esse collar (não forçar)

## Parâmetros atuais no banco

| Parâmetro | Valor | Plan sugere |
|-----------|-------|-------------|
| `limite_protecao_pct` | 0.0099 (1%) | 0.35 (35%) |
| `cab_minimo_protecao` | 1.0 | 1 |
| `fator_seguranca_liquidez` | 0.01 | 0.2 |
| `calda_preco_min_opcao` | 0.01 | 0.01 |
| `n_sigma_protecao` | 2.0 | 2.0 (obsoleto — trocar por breakeven)
