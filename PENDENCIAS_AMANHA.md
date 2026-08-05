# Pendências 06/08/2026

## Sessão OpenSpec — módulo 3: CalculadoraCaudaAssincrona

Prompt atualizado em `specs/SESSAO_OPENSPEC_PROMPT.md` (v2, 05/08/2026).

### Já concluídos
- ✅ Módulo 1: ParametroRepository (`specs/parametro_repository.md`) — aprovado
- ✅ Módulo 2: CalculadoraProtecaoCauda (`specs/calculadora_protecao_cauda.md`) — aprovado, correção de per-stage limits aplicada

### Próximo
- 🔜 Módulo 3: CalculadoraCaudaAssincrona (`src/domain/services/calculadora_cauda_assincrona.py`)

### Atenção especial (do prompt v2)
- **Contrato crítico:** os termos incrementais do grid de ratio DEVEM ser multiplicados por `qtd_acao` antes de somar a `pnl_projetado_base`. Bug histórico corrigido: versão original não fazia essa multiplicação (~1000x menor que o correto).
- Dependências: só o que aparece literalmente nos imports do arquivo.

---

## Correções aplicadas hoje (05/08/2026)

### mercado_data_provider.py (6 correções)
1. `of_compra_ativo`/`of_venda_ativo` no dict Onda 1
2. `ovd=0` não bloqueia mais o par
3. Manutenção OpenFAST usa call BID/ASK como proxy (sem CAB)
4. `_salvar_prioridades` salva Onda 1 + Onda 2
5. Background scan wrap → 0 (cobrindo índices baixos fora da prioridade)
6. `premio_put`/`premio_call` no dict Onda 1 (Collar via Onda 1)

### UI (3 correções)
7. Boleta TAXA: Ativo V(venda), Call C(compra), coeficiente positivo
8. Dialog TAXA: label "Compra Call" + preço BID real
9. monitor_worker.py: import `HistoricoSimulacoesRepository` (pós-processamento quebrava silenciosamente)

### calculadora_protecao_cauda.py
10. Per-stage limits implementados: Rendimento/Platô/Proteção usam limite específico, Base usa global
11. Testes atualizados: 4 testes em `TestLimitePorEstagio`

### calculadoras_dialog.py
12. OCR captura código ProfitPro + lookup banco + independente + always-on-top + CDI 140%

### Parâmetros
13. `premio_risco_colar`: 0.95 → 0.85 (JSON + banco)
14. Diversos parâmetros PROTECAO_CAUDA/PUT_RATIO/PERFORMANCE corrigidos
