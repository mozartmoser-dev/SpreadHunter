# Sessão 26/05/2026 — Calendar Collar: Modelo Coberto e Correções

**Objetivo:** Corrigir cálculo do Calendar Collar para modelo coberto (ação + opções) e alinhar com Profit Pro.

---

## ✅ Alterações Realizadas

### 1. Modelo Coberto (calculadora_colar_calendario.py)
- `capital_empregado` = S0 + Pp - Pc (custo de montagem com ação)
- `pnl_projetado` inclui perna da ação: `min(S0, Kc) - S0 + Pc + valor_put_vc - Pp`
- `pnl_stock` adicionado ao `ResultadoColarCalendario`
- %CDI agora realista (~1-2x) vs anterior (~14x)

### 2. Gráfico de Payoff (colar_calendario_dialog.py)
- Modelo coberto: `stock_pnl = np.minimum(x, Kc) - S0`
- Call: só prêmio (ação cobre exercício)
- Put: BS com DTE residual (não DTE cheio como antes — bug corrigido)
- Linhas sigma (±1σ, ±2σ) derivadas do IV da call

### 3. Gaussiano com Linha do Spot
- Linha vertical azul tracejada no centro (variação 0%) para conectar visualmente com payoff

### 4. Coluna % CDI na Grade
- Movida para 2ª posição (logo após Ativo)
- Coluna "Custo" (capital_empregado) adicionada na grade e nos detalhes

### 5. Correções de Bugs
- `atualizar_resultados` agora sempre reaplica filtro de ativos (não só em auto-mode)
- `data()` com try/except para evitar linhas em branco por erro de formatação
- `beginResetModel`/`endResetModel` em vez de `layoutChanged` para evitar linhas em branco

### 6. Interface
- Botões do rodapé renomeados: 🛡 Collar e 📅 Collar
- Botão "📋 Exportar Debug" adicionado no diálogo de detalhes
- Filtros DTE/%CDI com auto-restart do scanner
- Warning ao selecionar >20 ativos

### 7. Outputs Importantes da Sessão
- Melhor par encontrado: PETR4 Kcall=43.19 Kput=42.94, **2.06x CDI**, custo R$ 43.04
- Net crédito de entrada +R$ 0.18 (desconto na montagem)
- Strikes quase ATM (diferença centavos)

---

## 📌 Pendências
- Aferir valores calculados vs Profit Pro na prática
- Ajustar premio_risco padrão se necessário (atualmente 1.0x CDI)
- Verificar se linhas em branco no Collar tradicional foram resolvidas com beginResetModel
