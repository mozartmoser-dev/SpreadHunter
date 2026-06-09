# Regras de Negócio

## Strike de Opções

**NUNCA persista `strike` no banco de dados.** O strike de opções sofre ajustes
frequentes (ex-dividendo, desdobramento, grupamento). A única fonte confiável é o
RTD do Profit em tempo real. O campo `InstrumentoOpcional.strike` existe como
fallback opcional em memória, mas não deve ser lido/escrito no SQLite.

Se o RTD não fornecer strike em algum cenário, o sistema deve falhar ruidosamente
— não tentar adivinhar nem usar fallback do banco.

---

## Sessão Anterior (08/06/2026) — Pendências

### O que foi feito
1. **Background scan corrigido** (`mercado_data_provider.py`): reset do ponteiro ia para 0 em vez de `_background_offset` — impedia registrar mais de ~7.374 instrumentos. Agora registra todos (33.050).
2. **Blacklist atualizada**: +10 ativos (XPBR31, BACW39, BEEM39, BIAU39, BSLV39, AXIA98, GOLD11, SPXI11, NASD11, BOVV11). Total: 19 ativos.
3. **Filtros de `viavel` removidos** em todas as estratégias:
   - `monitor_colares.py:240` — Collar Protetivo
   - `monitor_box.py:155` — BOX 4P
   - `monitor_colares_calendario.py:248` — Collar Calendário
   - `monitor_worker.py:239-240` — Filtro de TP.Op removido
   - `viavel` continua sendo calculado, mas vira apenas cor de fundo na UI
4. **Logs de diagnóstico** adicionados no Collar:
   - `monitor_colares.py`: `Collar DIAG extrair` (contagem de filtros) + `Collar DIAG pares` (contagem de pares)
   - `calculadora_colar.py`: `Collar CALC` (motivo do reject)
5. **Collar automático ativado** (`monitor_worker.py`): `_colar_auto = True`, intervalo de 3 ciclos

### O que verificar na próxima sessão
1. **Rodar o sistema com Profit aberto** e capturar os logs `Collar DIAG`
2. **Analisar os logs** para identificar em qual etapa os collares estão sendo descartados:
   - `Collar DIAG extrair:` — mostra quantos passam em cada filtro (whitelist, strike, preco, qul, etc.)
   - `Collar DIAG pares:` — mostra quantos pares foram formados e quantos a calculadora rejeitou
   - `Collar CALC` — mostra o motivo exato do reject na calculadora
3. **Se o diagnóstico apontar `preco_compra_ativo` zerado** (ask do ativo via RTD), avaliar:
   - Usar `preco_ativo` (último preço) como fallback para o custo de compra da ação
   - Ou simplesmente exibir a informação para o usuário decidir
4. **Reverter `_colar_auto` para False** após o diagnóstico, se desejado
5. **Verificar performance** após correção do background scan (deve estar monitorando todos os 33.050+ instrumentos)

