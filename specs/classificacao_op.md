# ClassificacaoOp (enum)

## Propósito

Enum que classifica uma oportunidade detectada pelo scanner de acordo com a
estratégia que a originou. Determina como os indicadores financeiros são
interpretados e exibidos na UI (ex: uma oportunidade `1BOX` só mostra métricas
de BOX; `3BOXSBTH` mostra ambas).

## Contrato (Requisitos)

### `ClassificacaoOp.BOX_1` (`"1BOX"`)

**Garante:**
1. Oportunidade detectada exclusivamente como BOX (short box spread).
2. Na UI, exibe apenas indicadores de BOX (`pct_cdi_box`, `custo_box`, etc.).

### `ClassificacaoOp.SBTH_2` (`"2SBTH"`)

**Garante:**
1. Oportunidade detectada exclusivamente como SBTH (synthetic borrow trade hedge).
2. Na UI, exibe apenas indicadores de SBTH (`pct_cdi_sbth`, `custo_sbth`, etc.).

### `ClassificacaoOp.BOXSBTH_3` (`"3BOXSBTH"`)

**Garante:**
1. Oportunidade detectada simultaneamente como BOX e SBTH no mesmo instrumento.
2. Na UI, exibe ambos os conjuntos de indicadores, com o CDI máximo entre as
   duas estratégias.

### `ClassificacaoOp.TP_OP` (`"TP.Op"`)

**Garante:**
1. Classificação genérica para oportunidades que não se encaixam nas categorias
   acima (ex: "Outras").
2. Na UI (`OportunidadeMonitor.label_tipo`), exibe como `"Outras"`.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `enum` | `Enum` | Classe base |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 52 (compartilhado com Oportunidade) |
| Classes | 1 enum (4 membros) |
| Métodos/Funções | 0 |
| Complexidade ciclomática estimada | Mínima |
| Testes | Sim (indireto via `OportunidadeMonitor` e testes de UI) |

## Notas

- [2026-05-11 via git log] criado junto com `Oportunidade`. Última modificação: 2026-06-16.
- Definido no mesmo arquivo que `Oportunidade` (`src/domain/entities/oportunidade.py`).
- Os valores do enum (`"1BOX"`, `"2SBTH"`, `"3BOXSBTH"`, `"TP.Op"`) são usados
  como chaves de serialização no banco e como identificadores nos DTOs de UI
  (`OportunidadeMonitor.classificacao`).
- A lógica de classificação (decidir qual valor atribuir) está em
  `src/domain/rules/classificacao_oportunidade.py` (Camada 2), não neste enum.
