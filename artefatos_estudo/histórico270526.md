# Sessão 27/05/2026 — Botão "Explicar", Corrige Textos, Rodapé Payoff e Filtro Principal

**Objetivo:** Adicionar botão de explicação automática da estratégia, corrigir textos da explicação, adicionar info no rodapé dos gráficos de payoff, e corrigir prioridade do filtro da tela principal.

---

## ✅ Alterações Realizadas

### 1. Botão "🔍 Explicar" (colar_calendario_dialog.py)
- Novo método `gerar_explicacao()` estático em `CalculadoraColarCalendario`
- Gera HTML com: descrição da estratégia, montagem, tabela de 5 cenários (queda 30%/5%, estável, alta 5%/40%)
- Cada cenário mostra: PnL por perna, valor BS da put, intrínseco e extrínseco
- Botão "🔍 Explicar" no diálogo de detalhes, abrindo QDialog com QTextEdit renderizando o HTML

### 2. Correção de Bugs na Explicação
- **Lógica de exercício da put:** comparava `pnl_exercicio` com apenas `(put_bs - Pp)` em vez do PnL total sem exercício. Agora compara corretamente:
  - `pnl_no_ex = (S_T - S0) + Pc + (put_bs - Pp)`
  - `pnl_ex = (Kp - S0) + Pc - Pp`
- **Texto "lucro mínimo":** adaptado para mostrar "prejuízo" quando PnL negativo
- **Texto "expira sem valor":** agora verifica se put_bs < 0.01 para dizer "sem valor" vs "ainda vale R$ X"
- **Status ITM/OTM da CALL:** no cenário estável, verifica se S0 > Kc e mostra texto correto
- **Prêmio da CALL:** mostra intrínseco + extrínseco quando call está ITM
- **Resumo adaptável:** CALL ITM → resumo fala do extrínseco da CALL; CALL OTM → resumo fala do extrínseco residual da PUT

### 3. Rodapé nos Gráficos de Payoff
- **Collar Calendário:** ativo, spot, código+strike call (com prêmio), código+strike put (com prêmio), capital, PnL projetado com %CDI
- **Collar tradicional:** mesmo formato, com custo e pior retorno

### 4. Corrige Prioridade do Filtro da Tela Principal
- `_abrir_colar_calendario()` e `_abrir_colar()` agora verificam o `cmb_filter_ativo` **antes** de restaurar seleção salva
- Se o combo tiver um ativo específico (ex: PETR4), usa ele; só restaura seleção anterior se o combo estiver em "TODOS"

---

## 📁 Arquivos Modificados

| Arquivo | Alterações |
|---------|-----------|
| `src/domain/services/calculadora_colar_calendario.py` | +`gerar_explicacao()` (~120 linhas) |
| `src/ui/desktop/colar_calendario_dialog.py` | Botão "Explicar", método `_explicar_estrategia()`, rodapé no payoff |
| `src/ui/desktop/colar_dialog.py` | Rodapé no payoff |
| `src/ui/desktop/main_window.py` | Prioridade do filtro nos dois monitores |

---

## 📌 Pendências
- Melhorar performance da infraestrutura de importação de dados (RTD é o gargalo)
- Pensar em cache seletivo de instrumentos por ativo selecionado
