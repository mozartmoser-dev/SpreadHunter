# Relatório de Auditoria — Spreadhunter

**Data:** 24/07/2026  
**Escopo:** Varredura completa de cálculo, display e conformidade com a documentação de referência.  
**Resultado:** 527 testes passando, zero regressão.

---

## 1. O que foi auditado

O sistema foi comparado contra a documentação de referência das 6 estratégias de monitoramento: BOX comprado, SBTH comprada, TAXA comprada, BOX vendido, SBTH vendida, TAXA vendida.

**Regras de ouro verificadas:**

| Regra | Status |
|---|---|
| Bid/Ask — quem paga o quê (compra=ASK, venda=BID) | ✅ Conforme |
| Condição de viabilidade (custo < strike / recebimento > strike) | ✅ Conforme |
| Custos B3 sobre prêmio/preço (nunca strike) | ✅ Conforme |
| Fórmula de rentabilidade `(strike/custo - 1) / CDI` | ✅ Conforme |
| Leilão: identificar, não descartar | 🔧 Corrigido |
| Parâmetros no banco (nunca hardcoded) | 🔧 Corrigido |

---

## 2. Correções aplicadas (12 itens)

### 2.1 Cálculo (crítico)

| # | Problema | Arquivo |
|---|---|---|
| 1 | **Sinal invertido no PnL da Cauda Assíncrona.** Reduzir puts (ratio_put < 1) economiza prêmio — código subtraía em vez de somar. | `calculadora_cauda_assincrona.py` (4 locais) |
| 2 | **Breakeven (BE) usava `preco_ativo` como custo da ação** em vez de `preco_compra` (ASK real pago na compra). BE do gráfico divergia da curva. | `calculadora_colar_calendario.py` |
| 3 | **`theta_liquido = abs(θcall) - abs(θput)` falhava com put ITM.** Corrigido para `-θcall + θput`. | `calculadora_colar_calendario.py` |
| 4 | **Rentabilidade vendido usava `recebimento` como denominador.** Capital empatado é o `strike` (obrigação futura). Corrigido para `capital = strike`. | `monitor_vendidas.py`, `monitor_venda_coberta.py` (3 locais) |

### 2.2 Tooltips e display (alto)

| # | Problema | Descrição |
|---|---|---|
| 5 | `pct_cdi` e `pnl_projetado` diziam "custos incluídos" mas são valores brutos | Tooltips corrigidos |
| 6 | `net_credito` dizia "já descontados custos" mas nunca desconta | Tooltip corrigido |
| 7 | `pct_retorno` (bruto) exibido ao lado de `pnl_liquido` (líquido) no dialog | % líquida calculada corretamente |
| 8 | Diálogos Vendidas e Coberta não mostravam retorno líquido (B3+IR) | Adicionada linha de retorno líquido |

### 2.3 Leilão (alto)

| # | Problema | Descrição |
|---|---|---|
| 9 | **Leilão descartava operações** (`viavel = ... and not em_leilao`) | Removido de 7 locais. Operações em leilão agora aparecem com alerta ⚠️ LEILÃO |
| 10 | Alerta visual reforçado nos diálogos | "⚠️ LEILÃO" / "✓ Aberto" com fundo vermelho |

### 2.4 Novas funcionalidades

| # | O quê |
|---|---|
| 11 | **Coluna `★` (Qualidade)** — nota 1-5 agregando E[PnL], pnl_projetado, %CDI e Zona C |
| 12 | **Coluna `MOD`** — badge A/E (Americana/Europeia) com risco de exercício antecipado da CALL |
| 13 | **TAXA Comprada** — 6º monitor, mesma tabela que TAXA Vendida, diferenciado por coluna `Tipo` |

---

## 3. O que NÃO foi corrigido (e por quê)

| Item | Motivo |
|---|---|
| "Melhor estratégia" sem MAX() | **Decisão de design.** SBTH e BOX aparecem como linhas separadas — o trader pode escolher por praticidade de execução (2 vs 3 pernas), não apenas pelo maior número. |
| `_delta_pnl` com suposto erro de cap | **Falso positivo.** A perna da Call (`-n*max(0, S-Kc)`) já faz o cap — substituir `S-S_ref` por `min(S,Kc)` causaria double-count. Análise aprofundada refutou o achado. |
| BE butterfly com múltiplos cruzamentos | Sistema não usa mais BWB — não se aplica. |
| Snap de lote no Explicar | Corrigido pra mostrar quantidades sem round. |
| `risco_max` ignora naked call | Risk metric separada do payoff — necessita redesign, não correção pontual. |

---

## 4. Novos parâmetros (atenção)

Os seguintes parâmetros foram adicionados ao banco e PRECISAM ser populados (já foram via seed):

### 4.1 TAXA Comprada

| Chave | Valor | Descrição |
|---|---|---|
| `taxa_comprada_dist_max_pct` | 0.80 | Strike até 20% abaixo do ativo |
| `taxa_comprada_premio_risco` | 1.05 | ×CDI mínimo para viabilidade |
| `taxa_comprada_dias_maximos` | 10 | Prazo máximo em dias corridos |
| `taxa_comprada_lote_liquidez` | 1 | Lote mínimo de liquidez da CALL |

### 4.2 VENDIDAS (BOX + SBTH)

| Chave | Valor | Descrição |
|---|---|---|
| `vendidas_premio_risco` | 1.1 | ×CDI mínimo para BOX e SBTH vendidos |

### 4.3 VENDA COBERTA (TAXA Vendida)

| Chave | Valor | Descrição |
|---|---|---|
| `venda_coberta_dist_max_pct` | 0.0 | Sem distância mínima (aceita qualquer strike abaixo) |

> ⚠️ **Atenção:** `venda_coberta_dist_max_pct` foi alterado de `0.20` para `0.0`. Com o valor antigo, o sistema ignorava toda TAXA vendida com strike entre 80% e 100% do spot. O DB atualizado já reflete a correção.

### 4.4 Verificação

```powershell
python -c "from src.infrastructure.persistence.database import get_connection; c=get_connection(); rows=c.execute(\"SELECT chave,valor FROM parametros_operacionais WHERE estrategia IN ('TAXA_COMPRADA','VENDIDAS') OR chave='venda_coberta_dist_max_pct'\").fetchall(); [print(f'{r[0]} = {r[1]}') for r in rows]"
```

---

## 5. Status final

- **527 testes** passando (era 511 antes da auditoria)
- **6 monitores** em conformidade com as regras de ouro
- **Parâmetros** 100% no banco via `repo.get_by_chave()` — zero hardcoded
- **Leilão** identificado visualmente, sem descartar operações
- **Gráficos de payoff** com BE ajustado, range incluindo strikes de proteção, e filtro de falso toque no zero

### Fase 6 pendente

`historico_rejeicoes` — log qualificado de rejeições (liquidez, spread, custo, CDI) por estágio. Plano documentado, aguardando implementação.
