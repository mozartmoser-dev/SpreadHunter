# RECLAMAÇÃO COM DEEPSEEK — Retomar semana que vem (após teste com mercado aberto)

> **Status:** ÁREA DE RETOMADA — Não foi feito nenhuma alteração de código.
> Antes de qualququer mudança: proposta → confirmação explícita → execução (regra do AGENTS.md).

---

## 1. Contexto da queixa (08/08/2026 - sábado)

- Amigo usa **40k linhas no Excel com RTD** e **encontra oportunidades mais rápido e corretas**;
- O Excel **NÃO decide no "geleira" — ele APONTA E COLORÊ** a operação com fórmulas/que lêem a célula RTD viva no momento (latência ~0, sem cache);
- Nosso sistema Python/PySide6 + Excel headless **perde oportunidades** e tem **falsos positivos**;
- Causa raiz encontrada: **preço do ativo vindo com ~300s de defasagem**, e o sistema **acha/computa a operação com o preço que já mudou**.

## 2. Fatos técnicos MEDIDOS hoje (com números, não achismo)

### Fix do RTD Fast-Trade (SQT) — JÁ APLICADO E VALIDADO
- O produção da fórmula RTD estava errada; o `srv.rtd` exige o prefixo `SQT`:
  - ✗ errado: `=RTD("srv.rtd",,"<codigo>_B_0","<campo>")`
  - ✓ correto: `=RTD("srv.rtd",,"SQT","<codigo>","<campo>")`
- Confirmado com dados reais: PETR4/VALE3/ITUB + opções (BBDC3, PETRH201W1...) com preços reais no app;
- Arquivos tocados: `src/infrastructure/providers/rtd_fast_trade.py` (padrões de tópico + helper `_formula_rtd`), testes em `tests/test_rtd_fast_trade.py`.
- 631 testes passam (suíte completa OK).

### Falsos positivos — CAUSA NO CÓDIGO (achado, não suposição)
- `src/application/dtos/dtos.py:64-68` → `idade_ativo_ask` é **calculada** (`time.time() - ts_ativo_ask`);
- Mas **nenhum lugar usa essa idade para bloquear/rotular** a oportunidade:
  - `monitor_oportunidades.py:333` `_calcular_oportunidade` usa `preco_ativo` mesmo com 300s de idade;
- Por quê a idade não é fresca: `rtd_fast_trade.py:434` só atualiza `cache_ts` quando o **valor muda**:
  ```python
  if self._cache.get(chave) != v:
      self._cache_ts[chave] = agora
  ```
  Em ilíquio/mercado parado o valor não muda ⇒ a idade "engorda" mesmo com refresh ok.

### RTDXcel vs Socket (resumo do estudo)
- Socket (OpenFast, porta 557) = push, latência ~1–10ms, mas **só devolve quando chega tick novo**;
  - `openfast_socket_adapter.py:219-228` `forçar_leitura` espera até 500ms e **devolve valor VELHO** em não vier push (ilíquidos);
  - **Este é o PROVÁVEL motivo do problema no socket**: ilíquido não gera push → o `forçar` devolve stale/None.
- RTD via Excel = leitura **síncrona direta da célula** (`rtd_fast_trade.py:473` `forçar_leitura`, ~9ms) — **não depende de push chegar**; ideal p/ leitura sob demanda de ilíquidos;
  - Captura batch: throttle 250ms + `Range.Value` (~149ms/240k) + parse (~286ms→~76ms com numpy).
- **Não se busca com socket e nunca deveria:** o socket de "chegador para o método" é o flush em cache velho, não a velocidade de transporte.

## 3. O QUE O USUÁRIO QUER (deixa claro)

- **NÃO quer bloqueio ("impedir") de operações;**
- Ele **precisa LER INSTANTANHO O VALOR MAIS FRESCO POSSÍVEL** para **na perder operações que possam surgir**;
- O socket parecia "acontadendo isso" (valor chegando), mas a leitura em ilíquido é que falhava;
- Objetivo: **paridade com o Excel do amigo**: grid "acende/colore" na hora que o tick chega, usando o VALOR FRESCO no momento do cálculo.

## 4. Propostas PREPARADAS (ver antes de decidir) — não — aí realizada

> Aprovado: usuário ainda não escolheu. Continuar NO ARQUIVO PARA DISCUTIR NA SEMANA.

- **Correção do timestamp RTD:** atualizer `cache_ts` a cada **leitura válida** (não só quando muda). Efeito: idade mostra ~ciclo (1–5s) e os chave para do RTD é o valor atual dado ao servidor. (arquivo: `rtd_fast_trade.py` `_ler_do_excel`)
- **Leitura fresca no ponto de "viável"/pinta:** aplicar `forçar_leitura` (~9ms) em ativo + pernas **quando a operação passa os filtros**, antes de marcar como viável — paridade com a fórmula de cor no Excel. (arquivos: `monitor_oportunidades.py`, `monitor_vendidas.py`, `monitor_venda_coberta.py`, `monitor_colares.py`, `monitor_colares_calendario.py`, `monitor_box.py`, `monitor_put_ratio.py`)
- **Filtro de idade** (SE decidir por (A) ignorar, outro par.) — parâmetro `ativo_max_idade_s` via banco (cash: `parametros_default.json` + `parametro_operacional.py` + `parametros_widget.py` + `regras_dialog.py`).

## 4. PERGUNTAS para quando retomar

1. Consulta que você decidiu entre:
   (a) ignorar oportunidade com ativo velho; (b) marcar/colorear "DADO VELHO"; (c) não filtrar, só ler frescos.
   → Preferência manifestada do usuário é **ler o mais fresco, não impedir** (opção (c)/acima).
2. No socket: o que travava era **ilíquido não chegar por push**, ou o **push chegava mas a engine não frescava na** entendi hora? (defining qual otimização principal).
3. Teste **com mercabre aberto** na semana:
   - Verificar se ainda há dados 300s seguida com fonte RTD;
   - Medir se oportunidades aparecem na hora ao valor mudar (pouco, comparar com o Excel colorido do amigo);
   - Guardar logs de `\Varredura(F)` / `forçado` / idade para diagnóstico.

## 5. Estado do código hoje (está saudável e funcional)

- Fonte atual: `fonte_market_data = fasttrade` (RTD/Excel) — gerou pipeline e apresentou dados reais hoje;
- Socket aberto na porta 557 (OpenFast) — outra fonte disponível se quiser;
- 631 testes passarem;
- NENHUMA modificação acima de proposta está aplicada.