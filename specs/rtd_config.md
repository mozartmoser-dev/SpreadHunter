# rtd_config

Configuração estática do protocolo RTD do Profit: constantes de servidor, nomes de campos e o dataclass `DadosRTDInstrumento` que representa o snapshot completo de um par (CALL, PUT) + ativo após leitura do RTD.

## Contrato (Requisitos)

### Constantes de servidor
- `RTD_SERVIDOR = "rtdtrading.rtdserver"` — ProgID COM do servidor RTD do Profit.

### Constantes de campo
- `RTD_CAMPO_ULTIMO_PRECO = "ULT"` — último preço negociado.
- `RTD_CAMPO_STRIKE = "PEX"` — preço de exercício (strike).
- `RTD_CAMPO_VENCIMENTO = "VAL"` — data de vencimento.
- `RTD_CAMPO_OFERTA_VENDA = "OVD"` — oferta de venda (ask).
- `RTD_CAMPO_OFERTA_COMPRA = "OCP"` — oferta de compra (bid).
- `RTD_CAMPO_STATUS = "EST"` — status do ativo/opção.
- `RTD_CAMPO_CABECALHO_BOOK = "CAB"` — cabeçalho do book (indica se há book ativo).
- `RTD_CAMPO_QTDE_ULT_NEG = "QUL"` — quantidade do último negócio.
- `RTD_CAMPO_VOL_VENDA = "VOV"` — volume de venda (ask).
- `RTD_CAMPO_VOL_COMPRA = "VOC"` — volume de compra (bid).

### `rtd_topico(codigo: str) -> str`
**Garante:**
1. Formata o tópico RTD como `"CODIGO_B_0"` (sufixo `_B_0` indica book Bovespa nível 0).

### `DadosRTDInstrumento` (dataclass)
**Garante:**
1. Contém todos os campos lidos do RTD para um par (ativo, CALL, PUT): `ativo`, `cod_put`, `cod_call`, `preco_ativo`, `strike`, `vencimento_rtd`, `of_compra_ativo`, `of_venda_ativo`, `of_venda_put`, `of_compra_put`, `of_venda_call`, `of_compra_call`, `status_put`, `status_call`, `status_ativo`, `cab_put`, `qul_put`, `vov_put`, `cab_call`, `qul_call`, `voc_call`.
2. `premio_put` (property): retorna `of_venda_put` se > 0, senão `0.0`.
3. `premio_call` (property): retorna `of_compra_call` se > 0, senão `0.0`.
4. `em_leilao` (property): `True` se qualquer status (put, call, ativo) não for `"aberto"` (case-insensitive).
5. `to_dados_mercado()`: serializa para `dict` compatível com o formato esperado pelos use cases, incluindo `premio_put`, `premio_call`, `em_leilao`, `vov_put_boca`, `voc_call_boca`, `qul_put`, `qul_call`.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `dataclasses` | `dataclass` | Decorator do dataclass |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 86 |
| Última modificação | 2026-06-16 |
| Classes | 1 (`DadosRTDInstrumento`) |

## Notas

- 2026-06-16 — última modificação.
- O sufixo `_B_0` em `rtd_topico` indica "Bovespa, book nível 0". É específico do protocolo RTD do Profit.
- `premio_put` usa `of_venda_put` (ask da PUT) porque é o prêmio que o vendedor recebe. `premio_call` usa `of_compra_call` (bid da CALL) porque é o prêmio que o vendedor paga para recomprar. Isso segue a regra de negócio #6 do AGENTS.md.
- `to_dados_mercado()` converte `None` para `0.0` nos campos numéricos — os use cases downstream não lidam com `None`.
- `voc_call_boca` no `to_dados_mercado` mapeia `voc_call` (volume de compra da call) — nome "boca" é herdado do léxico do Profit.
