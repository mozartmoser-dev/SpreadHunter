# Histórico de Trabalho - Spreadhunter
**Data:** 24/05/2026
**Projeto:** Automação PNT (PlugNTrade)

---

## 🎯 PROBLEMA PRINCIPAL
Automação de preenchimento de boletas no PNT com velocidade e precisão, considerando que o mercado está fechado mas a interface deve funcionar.

---

## 📊 ANÁLISE DAS ABORDAGENS TESTADAS

### 1. Abordagem Original (28 passos via Tab)
- **Problema**: Muito arriscado, falha se houver lag no passo 15
- **Status**: ❌ Rejeitada

### 2. Abordagem por Coordenadas Fixas
- **Problema**: Falha se janela for movida ou resolução mudar
- **Status**: ❌ Rejeitada

### 3. Abordagem por Imagem (clicar cada campo)
- **Problema**: Lento, pyautogui demora para procurar cada campo
- **Status**: ❌ Rejeitada

### 4. Abordagem Híbrida (Solução Final) ✅
- **Método Primário**: `Ctrl+V` direto no campo Ativo
- **Fallback 1**: Botão de colar (pastinha)
- **Fallback 2**: Navegação via Tab
- **Vantagens**: Rápido, preciso, resiliente, 3 caminhos de fallback

---

## 🔧 IMPLEMENTAÇÃO REALIZADA

### Arquivos Modificados/Criados:

#### 1. `/src/infrastructure/integrations/pnt.py`
- **Modificação**: Método `enviar_oportunidade()`
- **Prioridades**:
  1. `Ctrl+V` no campo Ativo (método primário)
  2. Botão de colar (fallback)
  3. Navegação via Tab (último recurso)
- **Tempo**: Reduzido de ~28 passos para 1 `Ctrl+V`

#### 2. Scripts de Teste Criados:
- `scratch/test_pnt_ui_automation.py` (original)
- `scratch/calibrar_botao_colar.py` (calibração)
- `scratch/debug_botao.py` (depuração)
- `scratch/simple_test.py` (teste pyautogui)
- `scratch/scratch/manual_calibration.py` (calibração manual)
- `scratch/capture_botao_area.py` (captura de área)
- `scratch/test_clipboard.py` (teste clipboard)
- `scratch/test_ctrl_v.py` (teste Ctrl+V)
- `scratch/test_complete_flow.py` (teste completo)

### Testes Realizados:
- ✅ Clipboard e Ctrl+V funcionando corretamente
- ✅ pyautogui operando normalmente
- ✅ Formato de dados validado: `ATIVO;LADO;QUANTIDADE;PROFUNDIDADE`

---

## 📋 FORMATO FINAL DOS DADOS

### Estrutura enviada via Clipboard:
```
ATIVO;LADO;QUANTIDADE;PROFUNDIDADE
VALE3;C;100;0
VALEW280;C;100;1
VALEI280;C;100;1
```

### Campos preenchidos:
1. **Ativo**: Primeiro campo (via Ctrl+V)
2. **Lado**: Compra (C)
3. **Quantidade**: Parametrizada no banco
4. **Profundidade**: Parametrizada no banco
5. **Custo**: Ajustado manualmente após colagem

---

## 🚀 PRÓXIMOS PASSOS (amanhã)

### 1. Validação Real
- Testar com boleta do PNT aberta
- Verificar se todos os campos são preenchidos corretamente
- Ajustar tempos de espera se necessário

### 2. Otimização Final
- Ajustar tempos de sleep para melhor performance
- Validar formato exato esperado pelo PNT
- Testar com diferentes tipos de operações (BOX, SBTH, etc.)

### 3. Documentação
- Criar documentação de uso
- Descrever formatos de dados esperados
- Instruções de troubleshooting

---

## 🔍 OBSERVAÇÕES IMPORTANTES

### Vantagens da Solução Final:
- ⚡ **Velocidade**: `Ctrl+V` é instantâneo
- 🎯 **Precisão**: Não depende de coordenadas
- 🔧 **Resiliência**: 3 caminhos de fallback
- 🛡️ **Segurança**: Menos risco de erros

### Pontos de Atenção:
- O PNT deve estar aberto para receber o `Ctrl+V`
- O formato dos dados deve seguir exatamente o padrão `ATIVO;LADO;QUANTIDADE;PROFUNDIDADE`
- O tempo entre `Ctrl+V` e ajuste do custo pode precisar de ajuste fino

---

## 📂 ARQUIVOS PRINCIPAIS
- `pnt.py`: Integração principal (modificado)
- `test_complete_flow.py`: Script de teste final
- `test_clipboard.py`: Teste de funcionalidade base

---

**Status do Projeto:** ✅ Pronto para testes finais  
**Próxima Reunião:** Amanhã para testes e ajustes finais  
**Responsável:** Mozart

---

---

# Sessão 2 - Collar Calendário
**Data:** 25/05/2026

---

## 🎯 OBJETIVO
Implementar monitor de Collar Calendário no SpreadHunter: scanner, calculadora Black-Scholes, dialog com tabela e gráfico de payoff.

---

## ✅ CONCLUÍDO

### Arquitetura
- `calculadora_colar_calendario.py`: BS, IV (brentq), theta, `ResultadoColarCalendario`, `CalculadoraColarCalendario`
- `monitor_colares_calendario.py`: `MonitorColaresCalendarioUseCase.varrer()` — scanner com filtros DTE, pareamento call×put
- `colar_calendario_dialog.py`: Dialog com QTableView, filtro por ativos, detalhes, gráfico payoff matplotlib
- `monitor_worker.py`: Integração do scanner no loop principal da worker thread (intervalo 3 ciclos = ~7,5s)

### Problemas Identificados e Corrigidos
1. **Scanner só processa instrumentos com PEX em cache** (Onda 2 promovidos) — removeu-se assinatura sob demanda
2. **dte_extra**: valores exatos `[30, 60, 90]` → range `30-90` (aceita qualquer diferença entre vencimentos)
3. **premio_risco**: baixado de `1.0` para `0.0` no Collar Cal (qualquer PNL>0 é viável)
4. **Filtro por ativos**: dialog passa lista de ativos selecionados ao worker → `varrer(rtd, ativos=...)`
5. **Onda 2**: `MAX_REG_ONDA2_PER_CYCLE` aumentado de 40 para 200

### Descobertas
- `ConnectData` para OCP/OVD retorna `None` (sem exceção) quando não há cotação — ~1944/1949 instrumentos sem bid/ask
- Apenas 5 instrumentos têm OCP/OVD > 0 em VALE3 (3) e PETR4 (2), todos no DTE call (40-60), zero puts
- Collar Calendário depende de Onda 2 acumular dados (book+liquidez) para encontrar pares

---

## 🚧 PRÓXIMOS PASSOS

### Imediatos
- Aguardar Onda 2 completar (~700 instrumentos com book)
- Testar scanner Collar Cal com dados reais
- Validar se encontra pares viáveis (call+put com cotações)

### Futuros
- Persistir ativos com liquidez (para acelerar inicialização)
- Modelar cenários de IV na avaliação (não só BS com IV constante)
- Painel de desempenho do motor RTD

---

## 🔍 OBSERVAÇÕES IMPORTANTES
- Lucro do Collar Calendário: vender call + comprar put, desmontar no vencimento da call vendendo a put residual
- Projeção usa BS com IV constante — não capta mudanças de volatilidade
- Scanner NÃO assina RTD topics — só processa o que Onda 2 já popular
- Data atual: 25/05/2026 (maio de 2026)

---

## 📂 ARQUIVOS MODIFICADOS
- `src/application/use_cases/monitor_colares_calendario.py`: scanner principal
- `src/domain/services/calculadora_colar_calendario.py`: BS, IV, theta
- `src/ui/desktop/colar_calendario_dialog.py`: dialog com tabela e gráfico
- `src/ui/desktop/monitor_worker.py`: integração worker (intervalo 3, ativos filter)
- `src/ui/desktop/main_window.py`: signal/slot bridge
- `src/infrastructure/providers/mercado_data_provider.py`: Onda 2 batch 200
- `src/infrastructure/providers/rtd_profit.py`: (ajuste temp debug)

**Status:** ⏳ Aguardando Onda 2 acumular para teste real