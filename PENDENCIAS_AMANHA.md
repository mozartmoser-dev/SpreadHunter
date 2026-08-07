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

- [ ] **Fast Trade RTD:** pedir ao amigo ProgID e nomes de campos da fórmula `=RTD(...)` no Excel. Adaptar `RTDProfitAdapter` para Fast Trade (substituir Profit RTD COM).
- [ ] Auditoria de pipeline (log de rejeitados com motivo — discutido, não implementado)

## Concluído hoje (07/08)

- [x] `_is_weekly()` corrigido: `cod[-2] == 'W'` + `docs/codigos_b3.md`
- [x] Filtro `perf_filtro_semanal` — Onda 1 + Manutenção + UI
- [x] Ordenar instrumentos por vencimento (Onda 1 + background scan)
- [x] Bug `_determinar_operacao` BOXSBTH parcial → fallback individual (BOX/SBTH)
- [x] `ts_ativo_ask/bid` visível no DTO + ExportDialog + BoletaDialog + BoxDialog
- [x] Botão "Copiar Debug" em todos os diálogos
- [x] `inst.ativo in codigos_mudados` — push do ativo não era detectado
- [x] Re-registro OpenFast para ativos stale (>5s sem push, max 50/ciclo)
- [x] 6 parâmetros PROTEÇÃO_CAUDA alinhados (hardcoded = JSON = banco)
- [x] `perf_filtro_semanal` hardcoded alinhado (0.0 → 1.0)
- [x] Disclaimer.png
- [x] Lições aprendidas registradas no SKILL.md

## Estado atual

- 584 testes passando
- Sistema rodando normal (37k instrumentos com filtro semanal, ~50k sem)
- ~20 commits hoje, todos pushados
- ZIP diferencial enviado para o amigo (`diferencial_hoje.zip`)
