# TaxaAluguel

## Propósito

Entidade que armazena as taxas de aluguel de ações coletadas do InvestSite
para cada ativo monitorado. Contém a taxa atual, a média de 7 dias e a
média de 28 dias, permitindo ao sistema ajustar o custo de oportunidade
em estratégias que envolvem short selling sintético (SBTH, BOX).

`dataclass` com `slots=True`. Os dados são coletados pelo `InvestSiteClient`
e persistidos via `TaxaAluguelRepository`.

## Contrato (Requisitos)

### `TaxaAluguel(ativo, data, taxa_atual, taxa_7d, taxa_28d, ...)`

**Garante:**
1. `ativo: str` — ticker do ativo (ex: `"PETR4"`).
2. `data: date` — data da coleta.
3. `taxa_atual: float` — taxa de aluguel atual (% ao ano).
4. `taxa_7d: float` — média da taxa nos últimos 7 dias (% ao ano).
5. `taxa_28d: float` — média da taxa nos últimos 28 dias (% ao ano).
6. `created_at: datetime | None` — timestamp de criação do registro.
7. `id: int | None` — populado pelo repositório após INSERT.

## Dependências Diretas (por import)

| Módulo | Arquivo/Símbolo | Uso |
|--------|----------------|-----|
| `dataclasses` | `dataclass` | Decorador da classe |
| `datetime` | `date`, `datetime` | Tipos dos campos `data`, `created_at` |

**Não depende de nenhum módulo do projeto** (Kernel puro).

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas do arquivo | 13 |
| Classes | 1 |
| Métodos/Funções | 0 |
| Complexidade ciclomática estimada | Baixa |
| Testes | Sim (indireto via `TaxaAluguelRepository` e `InvestSiteClient`) |

## Notas

- [2026-07-05 via git log] módulo criado. Sem modificações posteriores.
- A coleta de taxas é condicional: controlada pelo parâmetro `taxa_aluguel_habilitado`
  (valor `1.0` = habilitado, `0.0` = desabilitado).
- As taxas são usadas como custo adicional em estratégias de short selling
  sintético. Se a taxa de aluguel for muito alta, o sistema pode filtrar
  oportunidades que dependem de venda de CALL coberta.
- `taxa_7d` e `taxa_28d` são médias calculadas pelo InvestSite, não pelo
  sistema — o `InvestSiteClient` apenas extrai os valores da página HTML.
