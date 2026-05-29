# Implementado com base no estudo do Gemini

## Arquivos de referência do Gemini
- `finance_math.py` — Motor matemático (dias úteis, feriados B3, VP)
- `estudo_base_opcoes.md` — Especificações técnicas e roadmap

## O que foi implementado

### 1. `src/domain/services/calendario_b3.py` (NOVO)
Módulo centralizado de conversão de tempo conforme padrão B3:
- `dc_to_du_aproximado(dias_corridos)` — Aproximação `round(dc * 252/365)`
- `dc_to_du_exato(data_inicio, data_fim)` — Dias úteis exatos via `np.busday_count` com calendário de feriados B3 (2024-2026)
- `dc_to_du(data_inicio, data_fim, dias_corridos)` — Híbrido: usa datas se disponíveis, fallback para aproximado
- `frac_du(dias_uteis)` → `dias_uteis / 252`
- `frac_dc(dias_corridos)` → `dias_corridos / 365`

### 2. Correção CDI para DU/252 nas 4 calculadoras

**Problema:** `calcular_cdi_periodo` usava `dias / 365`, mas CDI na B3 é taxa over capitalizada em 252 dias úteis.

**Arquivos alterados:**
- `src/domain/services/calculadora_colar_calendario.py` — `calcular_cdi_periodo(dias_uteis / 252)`
- `src/domain/services/calculadora_colar.py` — idem
- `src/domain/services/calculadora_box_sbth.py` — idem
- `src/domain/services/calculadora_vetorizada.py` — idem (versão numpy com `np.round(dias * 252/365)`)

### 3. UI — Rodapé CDI com DU + DC
- `src/ui/desktop/main_window.py:421-431` — Duas linhas no rodapé:
  ```
  CDI 14.50%a | 1.13%m
  DU 0.0537%d | DC 0.0374%d
  ```
  - Linha 1: anual + mensal (sem mudança)
  - Linha 2: DU/252 (oficial B3) + DC/365 (informativo)

### 4. UI — Debug export corrigido
- `src/ui/desktop/colar_calendario_dialog.py:722` — Conversão DC→DU antes do CDI

### 5. Calendário de feriados B3 dinâmico
**Problema:** `FERIADOS_B3` era lista fixa 2024-2026; viraria legacy em 2027.

**Solução (espelhando padrão dividendos):**
- `src/infrastructure/providers/feriados_b3_provider.py` (NOVO) — Busca feriados nacionais via **Brasil API** pública (`brasilapi.com.br/api/feriados/v1/{ano}`) + adiciona 9 de Julho (feriado SP, B3 fecha)
- `src/infrastructure/persistence/database.py` — Nova tabela `feriados_b3` com `UNIQUE(data)` e migração `_migrar_feriados_b3()` que sementeia dados iniciais
- `src/infrastructure/persistence/repositories/repositories.py` — Nova classe `FeriadoB3Repository` (save_batch com upsert, get_all, get_by_ano, delete_by_ano)
- `src/ui/desktop/feriados_dialog.py` (NOVO) — `QTableView` com colunas Data/Feriado/Tipo/Fonte/Atualizado, filtro por ano, botão Atualizar com `FeriadosFetchWorker` (QThread + progresso)
- `src/domain/services/calendario_b3.py` — Refatorado: `_feriados_atuais` mutável em vez de constante; `atualizar_calendario(lista)` e `carregar_do_banco(db_path)` para recarregar do DB com fallback para lista padrão
- `src/infrastructure/persistence/bootstrap.py` — Chama `carregar_do_banco()` após init
- `src/ui/desktop/main_window.py` — Novo botão "🗓 Feriados" que abre o dialog e recarrega calendário ao fechar

### 6. Testes
- `tests/domain/test_calculadora_colar_calendario.py` — 31 testes (Black-Scholes, theta, IV, CDI com DU/252, classificação, cálculo completo, explicação HTML)
- `tests/test_fase2.py` — Teste `cdi_periodo` adaptado para 252 DU

## O que NÃO foi alterado (deliberadamente)
- Black-Scholes (`T`, `implied_volatility`, `bs_theta`) — mantido DC/365 (sigma de mercado é calibrado em dias corridos)
- `dte_call`/`dte_put` no DTO — mantido como dias corridos (padrão para exibição na UI)
- Banco de dados (`oportunidades.cdi_periodo`) — registros históricos permanecem com valor DC/365

### 7. Ajuste de dividendos no Black-Scholes (correção Gemini item 5 — Risco 1)

**Problema:** BS superestima preço de calls quando há dividendos futuros (ex: PETR4). Sem ajuste, IV e theta da call ficam distorcidos.

**Solução:**
- `calculadora_colar_calendario.py` — Novo método estático `calcular_pv_dividendos(dividendos, S, r, dte_max)` que calcula `S_adj = S - Σ(div_i × e^(-r × t_i))`, filtrando dividendos passados e fora do prazo. `calcular()` aceita parâmetro opcional `dividendos: list[tuple[date, float]]`. `S_adj` usado em IV, theta e BS; `preco_ativo` (spot) mantido para classificação e PnL.
- `monitor_colares_calendario.py` — Busca dividendos futuros por ativo via `DividendoRepository.get_by_ativo()` e repassa para `calc.calcular(dividendos=...)`.
- `tests/domain/test_calculadora_colar_calendario.py` — 7 novos testes: sem dividendos, dividendo futuro, passado ignorado, fora do DTE, múltiplos, r=0, calcular() com dividendos retorna resultado.

**Comportamento seguro:** Se base desatualizada → sem dividendos no DB → `dividendos=[]` → `S_adj = S` → BS idêntico ao de hoje. Zero impacto. Só melhora quando há dados.

### 8. Underlying Bid/Ask no RTD (correção Gemini item 5 — Risco 2)
**Problema:** Ativo subjacente usava Último Preço (ULT) para capital empregado. Na prática, COMPRA-SE o ativo pelo ASK (OVD), não pelo ULT.

**Arquivos alterados:**
- `src/infrastructure/providers/rtd_config.py` — `DadosRTDInstrumento`: novos campos `of_compra_ativo`/`of_venda_ativo`; `to_dados_mercado()` agora usa valores reais em vez de `0.0`
- `src/infrastructure/providers/mercado_data_provider.py` — Registro de `OVD`/`OCP` para o ativo subjacente em `_registrar_ativos_prioritarios`, `_registrar_batch_inteligente`, `forcar_refresh_ex_dividendo`; leitura em `_ler_instrumento_cache`
- `src/domain/services/calculadora_colar.py` — `calcular()` aceita `preco_compra_ativo` opcional; usa Ask para capital empregado
- `src/domain/services/calculadora_colar_calendario.py` — Idem
- `src/application/use_cases/monitor_colares.py` — Lê `OVD` do ativo e passa como `preco_compra_ativo`
- `src/application/use_cases/monitor_colares_calendario.py` — Idem

**Efeito:** Oportunidades (SBTH/Box) já usavam `preco_compra_ativo` via `DadosMercado` — correção automática ao popular `of_venda_ativo`. Collars agora usam Ask para capital empregado, com fallback para ULT.

## Pendente para próxima iteração
- Migração de dados históricos do banco (opcional)

## Resultado dos testes
145/145 testes passando (7 novos: dividendos + 0 regressão).
