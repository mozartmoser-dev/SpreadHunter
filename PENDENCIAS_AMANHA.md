# Pendências — 07/08/2026 → 08/08/2026

## Specs Camada 2 — CONCLUÍDO (módulos 1-20)

Todas as 20 specs da Camada 2 geradas e aprovadas. Arquivos em `specs/`.

- `parametro_repository.md`
- `calculadora_protecao_cauda.md`
- `calculadora_cauda_assincrona.md`
- `instrumento_repository.md`
- `calculadora_colar_calendario.md`
- `calculadora_colar.md`
- `calculadora_put_ratio.md`
- `calculadora_vetorizada.md`
- `calculadora_box.md`
- `calculadora_box_sbth.md`
- `monitor_colares_calendario_use_case.md`
- `monitor_colares_use_case.md`
- `mpp_use_case.md`
- `monitor_oportunidades_use_case.md`
- `monitor_box_use_case.md`
- `monitor_put_ratio_use_case.md`
- `monitor_vendidas_use_case.md`
- `monitor_venda_coberta_use_case.md`
- `coletar_taxas_aluguel_use_case.md`
- `exportar_operacao_use_case.md`

Cadastro de notas de revisão em `inventory.md` (append-only).

## Correções aplicadas hoje (07/08)

### Pipeline / performance
- Bootstrap promove chave direto para `_chaves_com_book` (sem esperar manutenção)
- Manutenção roda ANTES do scan (nova chave entra no mesmo ciclo)
- Onda 1 não exige CALL BID (scanners filtram o que precisam)
- `of_venda_put`/`of_compra_call`/prêmios com `or 0.0` (evita NoneType)
- `bid_ativo = 0.0` quando BID inválido (evita falso positivo tipo EMBJ3)
- `_snapshot_pipeline` no worker (dialog não perde pipeline entre ciclos)
- Cap Onda 1 20k → REVERTIDO (desnecessário)
- Staleness 120s OpenFAST → REVERTIDO (matava operações em mercado calmo)
- `ts_ativo_ask`/`ts_ativo_bid` gravados no entry (auditoria)

### Cálculo
- `bs_put_ref` usa intrínseco no fallback sem BS (`calculadora_cauda_assincrona`)
- `save_batch` docstring avisa que `id` não é populado
- Taxa Vendida remove `dist_max_pct` 20% (era regra do SBTH)

### UI
- WIN/WDO contrato bimestral dinâmico (`mercado_topbar`)
- Toolbar agrupada: Calcs/Workspace/Simulações no menu Ferramentas
- Alt+C global para Calculadoras
- `Palette.TABLE_BG` adicionado

### Parâmetros
- `limite_protecao_pct*` corrigidos no banco + hardcoded + JSON
- `fator_seguranca_liquidez`, `spread_maximo_pct` corrigidos
- `perf_limite_meses`, `mre_profundidade_max_pct` alinhados

## Para amanhã

- [ ] Auditoria de pipeline (log de rejeitados com motivo — discutido, não implementado)
- [ ] `ts_ativo_ask/bid` expor em algum lugar visível (tooltip/pipeline)
- [ ] Corrigir `_is_weekly()` em `main_window.py:1747` — marca A,B,C,D,M,N,O,P (mensais Jan-Abr) como "S-" semanal. Correto: `W[1-9]$` no final do código.
- [ ] Filtro de opções semanais na Onda 1 (`mercado_data_provider.py:_deve_pular_instrumento()`), parâmetro `filtro_semanal` (0=incluir, 1=excluir). Usar `W[1-9]$` no sufixo do código, sem coluna nova no banco.
- [ ] Camada 1 (infraestrutura) — specs pendentes conforme inventário
- [ ] Camada 3 (UI) — specs pendentes conforme inventário

## Estado atual

- 582 testes passando
- Sistema rodando normal (50k instrumentos, 0 viáveis = mercado)
- 11 commits hoje, todos pushados
- ZIP diferencial enviado para o amigo (`diferencial_hoje.zip`)
