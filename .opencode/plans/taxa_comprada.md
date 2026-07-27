# Plano — TAXA Comprada (6º monitor)

**Objetivo:** Adicionar o monitor de TAXA comprada ao sistema, coexistindo com TAXA vendida na mesma tela, diferenciado por coluna `Tipo`.

---

## Regra de ouro

- **Fórmula:** `custo = of_venda_ativo - of_compra_call` (compra ativo no ASK, vende call no BID)
- **Condição de strike:** `strike <= preco_ativo * (1.0 - dist_max_pct)` onde `dist_max_pct` é parâmetro do banco (default 0.80 → 20% abaixo do ativo)
- **Condição de viabilidade:** `custo > 0` e `strike > custo`
- **Prazo:** `dias <= limite_dias` — parâmetro configurável (ex: 10 dias)
- **Rentabilidade:** `(strike/custo - 1) / cdi_periodo`
- **Leilão:** identificar, não descartar

---

## Arquivos a tocar

### 1. Parâmetros novos (3 arquivos)

**`config/parametros_default.json`** — adicionar:

```json
{"chave": "taxa_comprada_dist_max_pct", "valor": "0.80", "estrategia": "TAXA_COMPRADA", "descricao": "Distancia maxima do strike abaixo do ativo (1.0 = 0%, 0.80 = 20% abaixo)"},
{"chave": "taxa_comprada_premio_risco", "valor": "1.05", "estrategia": "TAXA_COMPRADA", "descricao": "Multiplo minimo do CDI para considerar viavel"},
{"chave": "taxa_comprada_dias_maximos", "valor": "10", "estrategia": "TAXA_COMPRADA", "descricao": "Prazo maximo em dias corridos para TAXA comprada"},
{"chave": "taxa_comprada_lote_liquidez", "valor": "1", "estrategia": "TAXA_COMPRADA", "descricao": "Lote minimo de liquidez para CALL"},
```

**`src/domain/entities/parametro_operacional.py`** — adicionar fallbacks:

```python
"taxa_comprada_dist_max_pct": {"valor": 0.80, "estrategia": "TAXA_COMPRADA", "descricao": "Distancia maxima do strike abaixo do ativo"},
"taxa_comprada_premio_risco": {"valor": 1.05, "estrategia": "TAXA_COMPRADA", "descricao": "Multiplo minimo do CDI"},
"taxa_comprada_dias_maximos": {"valor": 10, "estrategia": "TAXA_COMPRADA", "descricao": "Prazo maximo em dias corridos"},
"taxa_comprada_lote_liquidez": {"valor": 1, "estrategia": "TAXA_COMPRADA", "descricao": "Lote minimo de liquidez"},
```

**`src/ui/desktop/parametros_widget.py`** — adicionar `"TAXA_COMPRADA"` à sidebar, labels, tooltips e ranges.

---

### 2. Cálculo — `monitor_venda_coberta.py`

Adicionar método `varrer_comprada()` que itera sobre os mesmos `dados_mercado`:

```python
def varrer_comprada(self, dados_mercado: list[dict]) -> list[OportunidadeVendaCoberta]:
    dist_max_pct = self._ler_param_float("taxa_comprada_dist_max_pct", 0.80)
    premio_risco = self._ler_param_float("taxa_comprada_premio_risco", 1.05)
    limite_dias = self._ler_param_int("taxa_comprada_dias_maximos", 10)
    lote_liquidez = self._ler_param_int("taxa_comprada_lote_liquidez", 1)
    
    resultados = []
    for dados in dados_mercado:
        preco_ativo = dados["preco_ativo"]
        of_venda_ativo = dados.get("of_venda_ativo", 0)  # ASK do ativo
        of_compra_call = dados.get("of_compra_call", 0)  # BID da call
        strike = dados["strike"]
        dias = dados["dias"]
        cod_call = dados.get("cod_call", "")
        
        if dias > limite_dias:
            continue
        
        custo = of_venda_ativo - of_compra_call  # compra ativo ASK, vende call BID
        # ⚠️ NUNCA hardcoded: dist_max_pct vem do banco
        strike_max = preco_ativo * (1.0 - dist_max_pct)
        
        cond = (
            strike <= strike_max
            and custo > 0
            and strike > custo
            and of_venda_ativo > 0
            and of_compra_call > 0
        )
        if not cond:
            continue
        
        capital = abs(custo)
        pct = (strike - custo) / capital if capital > 0 else 0.0
        cdi_periodo = self._calcular_cdi_periodo(dias)
        pct_cdi = pct / cdi_periodo if cdi_periodo > 0 else 0.0
        
        em_leilao = dados.get("em_leilao", False)
        viavel = pct_cdi >= premio_risco  # leilão NÃO descarta, só identifica
        
        ... # custos B3 + IR (mesmo padrão da vendida)
        
        resultados.append(OportunidadeVendaCoberta(
            ativo=dados["ativo"],
            strike=strike,
            vencimento=dados["vencimento"],
            dias=dias,
            cod_put="",
            cod_call=cod_call,
            classificacao="TAXA_COMPRADA",
            recebimento=round(custo, 2),
            pct_ganho=round(pct, 6),
            pct_cdi=round(pct_cdi, 4),
            viavel=viavel,
            em_leilao=em_leilao,
            preco_ativo=round(preco_ativo, 2),
            of_venda_call=of_compra_call,  # atenção: inverte vs vendida
            custo=round(custo_b3, 2),
            pct_ganho_bruto=round(pct, 6),
            pct_ganho_liquido=round(pct_liq, 6),
            pct_cdi_bruto=round(pct_cdi, 4),
            pct_cdi_liquido=round(pct_cdi_liq, 4),
            detectado_em=agora,
        ))
    
    return resultados
```

---

### 3. DTO — `dtos_venda_coberta.py`

Adicionar ao `classificacao` ou property `label_tipo`:

```python
@property
def label_tipo(self) -> str:
    if self.classificacao == "TAXA_COMPRADA":
        return "TAXA COMPRADA"
    return "TAXA"
```

---

### 4. Tabela — `venda_coberta_table_model.py`

- Manter o mesmo modelo de tabela
- Coluna `Tipo` (label_tipo) para distinguir VENDIDA × COMPRADA
- TAXA vendida: `of_venda_call` = ASK (você paga)
- TAXA comprada: `of_compra_call` = BID (você recebe)

---

### 5. Pipeline — `monitor_worker.py`

No método `_varrer_coberta()` (linhas ~386-395), chamar ambos:

```python
def _varrer_coberta(self):
    dados = self._coletar_dados_mercado_coberta()
    vendidas = self._monitor_coberta_uc.varrer(dados)
    compradas = self._monitor_coberta_uc.varrer_comprada(dados)
    todas = vendidas + compradas
    self.oportunidades_coberta_atualizadas.emit(todas)
```

Ou emitir em sinais separados se preferir abas diferentes.

---

### 6. UI — `main_window.py`

- A tabela de TAXA (venda coberta) já existe
- Linhas de TAXA comprada aparecem na mesma tabela, diferenciadas pela coluna `Tipo`
- Cores diferentes para background: TAXA vendida (existing), TAXA comprada (nova)

---

## Ordem de implementação

| Passo | O que | Testável? |
|---|---|---|
| 1 | Parâmetros: JSON + entity + widget | Sim — `repo.get_by_chave("taxa_comprada_dist_max_pct")` |
| 2 | `varrer_comprada()` no use case | Sim — mock `dados_mercado` |
| 3 | DTO + coluna `Tipo` na tabela | Sim — teste de display |
| 4 | Integração no `monitor_worker` | Só com RTD real |
| 5 | Testes ponta-a-ponta | Só com RTD real |

---

## ⚠️ Atenção

- **NUNCA hardcodar 0.80** — usar `taxa_comprada_dist_max_pct` do banco
- **NUNCA hardcodar 10 dias** — usar `taxa_comprada_dias_maximos` do banco
- `of_venda_ativo` precisa existir nos dados de mercado — verificar se Onda 1/2 populam este campo (atualmente `of_compra_ativo` existe, `of_venda_ativo` pode precisar ser adicionado ao provider)
- Custos B3: usar `preco_ativo` (ASK de compra) para custo stock, `of_compra_call` (BID recebido) para custo opção
