# Regras de Negócio

## Strike de Opções

**NUNCA persista `strike` no banco de dados.** O strike de opções sofre ajustes
frequentes (ex-dividendo, desdobramento, grupamento). A única fonte confiável é o
RTD do Profit em tempo real. O campo `InstrumentoOpcional.strike` existe como
fallback opcional em memória, mas não deve ser lido/escrito no SQLite.

Se o RTD não fornecer strike em algum cenário, o sistema deve falhar ruidosamente
— não tentar adivinhar nem usar fallback do banco.

---

## Sessão 09/06/2026 — Correções Estruturais

### O que foi feito

#### Custos B3 (Crítico)
- **Base trocada**: todas as 5 calculadoras usavam `strike` como base para custos B3. Agora usam **prêmio da opção** (opções) e **preço da ação** (ações), conforme tarifário oficial da B3.
- **Ida-e-volta**: custos agora consideram entrada + saída (×2).
- **Collars**: perna de ação (`custos_stock`) estava ausente — agora incluída.
- `calculadora_custos_b3.py`: novos métodos `custos_opcao()`, `custos_stock()`, `taxa_total_stock()`.
- `calculadora_colar_calendario.py`: removido `max(pnl - custo, 0.0)` — perdas propagam corretamente.

#### Performance — CAB Skip
- Wave 2 instruments agora leem só CAB (2 leitores). Se não mudou, reusam cache e atualizam apenas status.
- Fast scan medido: **0.04s** (vs ~4.66s global scan inicial).
- `mercado_data_provider.py`: `_cab_anterior` + `_dados_cache`.

#### Ex-Dividendo — DisconnectData
- `invalidar_cache()` agora faz `DisconnectData` + remove de `_topic_map`/`_topic_reverse`. `registrar_topico()` gera **novo topic ID** — equivalente ao "recorta-cola" que funcionava no Excel.
- `forcar_refresh_ex_dividendo()` limpa `_cab_anterior` e `_dados_cache` para forçar refresh completo.

#### UI
- Tooltips em todas as colunas (monitor, box, collar, collar calendário, MPP).
- Ordem de colunas persiste entre sessões via QSettings (`column_utils.py`).
- `_colar_auto = False` (revertido após diagnóstico).

#### Correções anteriores mantidas
- Background scan corrigido (33k+ instrumentos).
- Filtros `viavel` removidos (cosmético apenas).
- Logs `Collar DIAG` / `Collar CALC`.
- TP.Op filter restaurado.
- Ganhos negativos propagam sem caps.
- IR split worst/best case no collar.

### Próximos passos
1. Rodar com Profit aberto em horário de mercado para validar collares e performance final.
2. Se necessário: investigar fallback de strike via API B3 para dividendos overnight.

