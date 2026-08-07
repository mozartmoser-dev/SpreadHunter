# Oportunidade

## Propósito

Entidade que representa uma oportunidade de arbitragem detectada pelo scanner
(BOX, SBTH, ou ambas). Persiste na tabela `oportunidades` com os indicadores
financeiros calculados (custos, % ganho, % CDI) e um `snapshot_mercado` para
diagnóstico post-mortem.

`dataclass` com `slots=True`. O campo `snapshot_mercado` é um dict livre que
armazena o estado do book no momento da detecção — serve para auditoria e
debug, não para cálculos em tempo real.

## Contrato (Requisitos)

### `Oportunidade(instrumento_id, preco_ativo, strike, dias, cdi_periodo, ...)`

**Garante:**
1. `instrumento_id: int` — FK para `instrumentos_base.id`.
2. `preco_ativo: float` — preço do ativo-objeto no momento da detecção.
3. `strike: float` — strike da PUT (fonte: RTD, NUNCA do sufixo B3).
4. `dias: int` — dias corridos até o vencimento.
5. `cdi_periodo: float` — fator CDI acumulado no período (ex: 1.0012 para 0.12%).
6. `custo_sbth: float`, `pct_ganho_sbth: float`, `pct_cdi_sbth: float` —
   indicadores da estratégia SBTH.
7. `custo_box: float`, `pct_ganho_box: float`, `pct_cdi_box: float` —
   indicadores da estratégia BOX.
8. `classificacao: ClassificacaoOp` — enum: `1BOX`, `2SBTH`, `3BOXSBTH`, `TP.Op`.
9. `operacao: str` — descrição textual da operação.
10. `snapshot_mercado: dict` — campo livre com `field(default_factory=dict)`.
    Armazena estado do book no momento da detecção. NÃO use para cálculos.
11. `id: int | None` — populado pelo repositório após INSERT.

### `liq_put_x_lote` (property)

**Garante:**
1. Lê `snapshot_mercado.get("liq_put_x_lote", 0.0)`.
2. Retorna `float`.

### `liq_call_x_lote` (property)

**Garante:**
1. Lê `snapshot_mercado.get("liq_call_x_lote", 0.0)`.
2. Retorna `float`.

### `em_leilao` (property)

**Garante:**
1. Lê `snapshot_mercado.get("em_leilao", False)`.
2. Retorna `bool`.

### `status_put` (property)

**Garante:**
1. Lê `snapshot_mercado.get("status_put", "")`.
2. Retorna `str`.

### `status_call` (property)

**Garante:**
1. Lê `snapshot_mercado.get("status_call", "")`.
2. Retorna `str`.

### `status_ativo` (property)

**Garante:**
1. Lê `snapshot_mercado.get("status_ativo", "")`.
2. Retorna `str`.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `dataclasses` | `dataclass`, `field` | Decorador, `default_factory` |
| `enum` | `Enum` | `ClassificacaoOp` (definido no mesmo arquivo) |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 52 |
| Classes | 2 (Oportunidade + ClassificacaoOp no mesmo arquivo) |
| Métodos/Funções | 6 properties (liq_put_x_lote, liq_call_x_lote, em_leilao, status_put, status_call, status_ativo) |
| Complexidade ciclomática estimada | Baixa |
| Testes | Sim (indireto via `TestOportunidadeRepository` e fixtures) |

## Notas

- [2026-05-11 via git log] módulo criado. Última modificação: 2026-06-16.
- `snapshot_mercado` usa `field(default_factory=dict)` — o padrão Python para
  campos mutáveis em dataclasses (evita compartilhamento de instância).
- As 6 properties são todas delegações para `snapshot_mercado.get()` com
  defaults seguros. Servem para evitar `KeyError` ao acessar campos que podem
  não existir no snapshot (ex: snapshots antigos sem `em_leilao`).
- A entidade NÃO contém lógica de cálculo — os percentuais (`pct_ganho_*`,
  `pct_cdi_*`) são pré-calculados pelas calculadoras e armazenados como
  campos planos.
- O campo `classificacao` usa o enum `ClassificacaoOp` definido no mesmo
  arquivo. A serialização do repositório usa `.value` (ex: `"1BOX"`).
