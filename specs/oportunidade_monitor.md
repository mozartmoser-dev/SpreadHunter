# OportunidadeMonitor (DTO)

## Propósito

DTO que transporta uma oportunidade detectada do `MonitorWorker` para a UI
(`main_window.py`). É uma versão "achatada" de `Oportunidade` + dados do
`InstrumentoOpcional`, enriquecida com preços de book, liquidez, moneyness
e taxas de aluguel — tudo o que a tabela de resultados precisa exibir sem
fazer novas queries.

Inclui properties de formatação para exibição na UI (`label_rentabilidade`,
`ganho_bruto_display`, etc.) e classificação por tipo (`is_box`, `is_sbth`,
`label_tipo`).

## Contrato (Requisitos)

### `OportunidadeMonitor(instrumento_id, ativo, strike, vencimento, dias, cod_put, cod_call, tipo_opcao, ...)`

**Garante:**
1. Campos de identificação: `instrumento_id`, `ativo`, `strike`, `vencimento`,
   `dias`, `cod_put`, `cod_call`, `tipo_opcao` (string, valor do enum).
2. Campos de classificação: `classificacao` (default `""`), `operacao` (default `""`).
3. Indicadores SBTH: `custo_sbth`, `pct_ganho_sbth`, `pct_cdi_sbth`,
   `pct_cdi_sbth_liquido`, `pct_ganho_sbth_bruto`, `pct_ganho_sbth_liquido`,
   `pct_cdi_sbth_bruto` — todos default `0.0`.
4. Indicadores BOX: `custo_box`, `pct_ganho_box`, `pct_cdi_box`,
   `pct_cdi_box_liquido`, `pct_ganho_box_bruto`, `pct_ganho_box_liquido`,
   `pct_cdi_box_bruto` — todos default `0.0`.
5. Campos de book: `preco_compra_ativo`, `of_venda_put` (ASK), `of_compra_call`
   (ASK), `of_compra_put` (BID), `of_venda_call` (BID) — todos default `0.0`.
6. Liquidez: `qul_put`, `qul_call`, `liq_put_x_lote`, `liq_call_x_lote` —
   todos default `0.0`.
7. Moneyness: `money_put`, `money_call` — default `0.0`.
8. Outros: `cdi_periodo`, `viavel`, `em_leilao`, `taxa_aluguel` — defaults
   apropriados.
9. `detectado_em: datetime | None` — timestamp de detecção (UTC).

### `label_detectado` (property)

**Garante:**
1. Se `detectado_em is None`, retorna `""`.
2. Converte UTC → America/Sao_Paulo via `zoneinfo.ZoneInfo`.
3. Formata como `"%d/%m/%Y %H:%M:%S"` (horário de Brasília).

### `custo_sbth_display` (property)

**Garante:**
1. Se `custo_sbth > 0`, retorna formatado com 2 casas decimais.
2. Caso contrário, retorna `"-"`.

### `custo_box_display` (property)

**Garante:**
1. Se `custo_box > 0`, retorna formatado com 2 casas decimais.
2. Caso contrário, retorna `"-"`.

### `is_box` (property)

**Garante:**
1. `True` se `classificacao in ("1BOX", "3BOXSBTH")`.

### `is_sbth` (property)

**Garante:**
1. `True` se `classificacao in ("2SBTH", "3BOXSBTH")`.

### `label_tipo` (property)

**Garante:**
1. Mapeia classificação para label legível: `"1BOX"` → `"BOX"`,
   `"2SBTH"` → `"SBTH"`, `"3BOXSBTH"` → `"BOX+SBTH"`, `"TP.Op"` → `"Outras"`.

### `label_rentabilidade` (property)

**Garante:**
1. Exibe o múltiplo do CDI para a estratégia detectada, com versão líquida
   entre parênteses se disponível.
2. Para `3BOXSBTH`, usa `max(pct_cdi_box, pct_cdi_sbth)`.

### `ganho_bruto_display` (property)

**Garante:**
1. Exibe percentual de ganho bruto multiplicado por 100.
2. Para `3BOXSBTH`, mostra ambos: `"X.XX% (SBTH) | Y.YY% (BOX)"`.

### `ganho_liq_display` (property)

**Garante:**
1. Análogo a `ganho_bruto_display` para ganho líquido.

### `rent_cdi_bruto_display`, `rent_cdi_liq_display` (properties)

**Garante:**
1. Exibem % CDI bruto/líquido multiplicado por 100.

### `label_dias` (property)

**Garante:**
1. Retorna `"{dias}d"`.

### `money_display` (property)

**Garante:**
1. Se `money_put > 0`, prefixa `"P:{:.2f}"`.
2. Se `money_call > 0`, prefixa `"C:{:.2f}"`.
3. Junta com `" | "` se ambos presentes.

### `resumo_linha` (property)

**Garante:**
1. Retorna string de uma linha com ativo, tipo, dias, vencimento,
   rentabilidade e % ganho — formato compacto para logs e notificações.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `dataclasses` | `dataclass`, `field` | Decorador, `default_factory` |
| `datetime` | `date`, `datetime` | Tipos dos campos `vencimento`, `detectado_em` |
| `enum` | `Enum` | `TipoExportacao` (definido no mesmo arquivo, não usado por este DTO) |
| `zoneinfo` | `ZoneInfo` | Import lazy dentro de `label_detectado` |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 227 (compartilhado com 4 outros DTOs + 1 enum) |
| Classes | 1 dataclass |
| Métodos/Funções | 16 properties de display |
| Complexidade ciclomática estimada | Média (múltiplas branches de classificação) |
| Testes | Sim (indireto via use cases e testes de UI) |

## Notas

- [2026-05-11 via git log] criado. Última modificação: 2026-07-29.
- `zoneinfo.ZoneInfo` é importado lazy (dentro de `label_detectado`) — evita
  dependência de `tzdata` no namespace do módulo.
- As properties de display duplicam lógica de classificação (`1BOX`, `2SBTH`,
  `3BOXSBTH`) em múltiplos métodos — se uma nova classificação for adicionada,
  todas as properties precisam ser atualizadas.
- `detectado_em` é armazenado em UTC e convertido para Brasília apenas na
  exibição — consistente com boas práticas de timezone.
- O DTO não contém lógica de negócio, apenas formatação para UI.
