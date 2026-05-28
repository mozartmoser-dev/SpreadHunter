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

### 3. UI — CDI diário corrigido
- `src/ui/desktop/main_window.py:421` — `(1 + taxa_cdi) ** (1/252) - 1`

### 4. UI — Debug export corrigido
- `src/ui/desktop/colar_calendario_dialog.py:722` — Conversão DC→DU antes do CDI

### 5. Testes
- `tests/domain/test_calculadora_colar_calendario.py` — 31 testes (Black-Scholes, theta, IV, CDI com DU/252, classificação, cálculo completo, explicação HTML)
- `tests/test_fase2.py` — Teste `cdi_periodo` adaptado para 252 DU

## O que NÃO foi alterado (deliberadamente)
- Black-Scholes (`T`, `implied_volatility`, `bs_theta`) — mantido DC/365 (sigma de mercado é calibrado em dias corridos)
- `dte_call`/`dte_put` no DTO — mantido como dias corridos (padrão para exibição na UI)
- Banco de dados (`oportunidades.cdi_periodo`) — registros históricos permanecem com valor DC/365

## Pendente para próxima iteração
- Mostrar ambos os valores na UI (DU/252 como primário, DC/365 como informativo)
- Migração de dados históricos do banco (opcional)
- Calendário de feriados B3 dinâmico (via API ANBIMA)

## Resultado dos testes
138/138 testes passando (31 novos + 107 existentes).
