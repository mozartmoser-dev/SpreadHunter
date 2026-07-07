# SpreadHunter — Tuning de Performance: Onda 1 e Onda 2

**Data:** Junho 2026  
**Escopo:** `mercado_data_provider.py`, `rtd_profit.py`, `monitor_worker.py`, `database.py`  
**Base analisada:** 35.772 instrumentos (10 vencimentos), DB `spreadhunter.db`

---

## 1. Diagnóstico: O Que Está Lento e Por Quê

### 1.1 Causa Primária — `RefreshData(0)` é Síncrono e Sem Timeout

A chamada COM `self._rtd.RefreshData(0)` no `rtd_profit.py` é síncrona e bloqueante. O Python fica travado aguardando resposta do servidor RTD do Profit Pro — sem timeout configurável na camada COM. Evidência dos logs:

| Log | Fast avg | Global avg |
|-----|----------|------------|
| log.4 (6 dias atrás) | **0.244s** | 2.87s |
| log.1 (2 dias atrás) | **1.510s** | 6.28s |
| log (hoje) | **1.897s** | 6.18s |

Fast scan subiu ~8x. Isso significa que **a degradação não é código Python** (que seria consistente) — é latência COM/Profit absorvendo o ciclo inteiro.

### 1.2 Causa Secundária — `get_all_mapped()` Chamado DUAS VEZES por Ciclo

Em `capturar_dados_mercado()` há duas chamadas ao banco:

```python
# Linha 284 — dentro do bloco de registro
instrumentos = self.inst_repo.get_all()          # 1ª consulta (35k rows)

# Linha 319 — na varredura principal
inst_map = self.inst_repo.get_all_mapped()        # 2ª consulta (35k rows, mesmo cache)
```

O `InstrumentoRepository` tem cache de classe (`_cache_all`, `_cache_mapped`), então a segunda chamada é free se o cache estiver quente. **O problema é que `recarregar_parametros()` chama `_chaves_com_book.clear()` sem invalidar o cache do repositório**, e `recarregar_instrumentos()` chama `invalidate_cache()` forçando uma releitura completa das 35k linhas no próximo ciclo. Se parâmetros forem alterados com frequência, isso acumula I/O.

### 1.3 Causa Terciária — Onda 1 Itera 35k Instrumentos no Loop Principal

No ciclo Global (a cada 10 iterações), `chaves_alvo = self._chaves_registradas` — ou seja, até 35k chaves são varridas em Python puro. Para cada chave, fazem-se chamadas a `inst_map.get(key)` e depois uma sequência de `ler_campo_cache()`. Mesmo sendo lookup de dict, com 35k entradas por ciclo de 2,5s isso consome tempo real.

### 1.4 Acúmulo de `mpp_snapshot` Sem Limpeza

A tabela `mpp_snapshot` já tem **11.329 linhas** e cresce a cada execução MPP (3.353 rows hoje, 4.942 na última semana). Não há DELETE/TRUNCATE periódico. Com `synchronous=FULL (2)` e `cache_size=-2000 KB`, writes frequentes nessa tabela geram flush de WAL desnecessário durante a varredura.

### 1.5 Onda 2 com Limite de 500 por Ciclo — Certo, Mas Desacoplado

`MAX_REG_ONDA2_PER_CYCLE = 500` limita corretamente os registros RTD por ciclo. Porém, tanto `capturar_dados_mercado()` quanto `fazer_manutencao()` fazem Onda 2 de forma independente, potencialmente duplicando trabalho em ciclos de manutenção (a cada 10).

### 1.6 `synchronous = 2 (FULL)` — Conservador Demais Para WAL

Com `journal_mode=WAL`, o modo seguro suficiente é `synchronous=NORMAL (1)`. O modo FULL força um fsync extra a cada commit, desnecessário no WAL onde a durabilidade já é garantida pelo checkpoint.

---

## 2. Sugestões de Melhoria — Ordenadas por Impacto

---

### SUGESTÃO 1 — Thread Watchdog para `RefreshData` com Timeout  ⭐⭐⭐ (Impacto Alto)

**Arquivo:** `src/infrastructure/providers/rtd_profit.py`

O `RefreshData(0)` hoje trava o ciclo inteiro quando o Profit demora. A solução é rodar a chamada COM em uma thread separada com timeout, retornando o último cache quando exceder o limite.

**Implementação proposta:**

```python
import threading

class RTDProfit:
    def __init__(self):
        # ... código existente ...
        self._refresh_timeout_s: float = 2.0   # ajustável
        self._ultimo_resultado_refresh: dict = {}

    def refresh(self) -> dict[str, object]:
        if not self.disponivel or self._rtd is None:
            return {}

        resultado_container = [None]
        erro_container = [None]

        def _chamar_refresh():
            try:
                resultado_container[0] = self._rtd.RefreshData(0)
            except Exception as e:
                erro_container[0] = e

        t = threading.Thread(target=_chamar_refresh, daemon=True)
        t.start()
        t.join(timeout=self._refresh_timeout_s)

        if t.is_alive():
            # RefreshData travou — retorna cache anterior sem bloquear
            logger.warning("RTD RefreshData timeout (>%.1fs) — usando cache anterior.", self._refresh_timeout_s)
            return {}  # ciclo usa ler_campo_cache() com dados do ciclo anterior

        if erro_container[0]:
            logger.debug("RTD RefreshData erro: %s", erro_container[0])
            return {}

        # Processamento normal do resultado...
        resultado = resultado_container[0]
        # [continua o parsing existente de data/update_count/topics/values]
```

> **Atenção COM/threading:** O Profit RTD cria o objeto no apartment thread (o QThread do MonitorWorker). Chamar `RefreshData` de uma thread nova exige que essa thread inicialize COM com `pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)` **ou** que se passe o ponteiro marshaled com `CoMarshalInterThreadInterfaceInStream`. A opção mais simples: usar `COINIT_MULTITHREADED` na thread watchdog e testar com o Profit — na prática muitos servidores RTD aceitam MTA para leitura.

---

### SUGESTÃO 2 — `RefreshData` Seletivo: Só Tópicos com Book  ⭐⭐⭐ (Impacto Alto)

**Arquivo:** `src/infrastructure/providers/rtd_profit.py`

Hoje `RefreshData(0)` pede atualização de **todos** os tópicos registrados — incluindo os ~35k tópicos CAB (cabeçalho) da Onda 1 que raramente mudam. A API RTD suporta passar uma lista de topic IDs.

**Implementação proposta:**

```python
def refresh_seletivo(self, tids_prioritarios: list[int]) -> dict[str, object]:
    """Refresha apenas os tópicos da lista (Onda 2 + ativos)."""
    if not self.disponivel or self._rtd is None:
        return {}
    try:
        # Passa array de topic IDs em vez de 0 (todos)
        resultado = self._rtd.RefreshData(len(tids_prioritarios), tids_prioritarios)
    except Exception as e:
        logger.debug("RTD RefreshData seletivo erro: %s", e)
        return {}
    # ... parsing idêntico ao refresh() atual ...
```

No `MercadoDataProvider`, substituir:

```python
# ANTES
self.rtd.refresh()

# DEPOIS — Fast scan usa apenas tids com book
if is_global_scan:
    self.rtd.refresh()                                    # completo a cada 10 ciclos
else:
    tids_book = self._coletar_tids_com_book()             # só Onda 2
    self.rtd.refresh_seletivo(tids_book)
```

Onde:

```python
def _coletar_tids_com_book(self) -> list[int]:
    tids = []
    for key in self._chaves_detalhes_completos:
        inst = self._inst_map_cache.get(key)
        if inst:
            for campo in [RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_OFERTA_COMPRA,
                          RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_STRIKE]:
                tid = self.rtd._topic_map.get(f"{inst.cod_put}|{campo}")
                if tid: tids.append(tid)
                tid = self.rtd._topic_map.get(f"{inst.cod_call}|{campo}")
                if tid: tids.append(tid)
    return tids
```

> Se `_chaves_detalhes_completos` tiver 500 instrumentos → ~4.000 tids vs os 300k+ tids do refresh total. Redução de carga RTD de ~75x nos Fast scans.

---

### SUGESTÃO 3 — Eliminar Segunda Chamada `get_all_mapped()` no Ciclo  ⭐⭐ (Impacto Médio)

**Arquivo:** `src/infrastructure/providers/mercado_data_provider.py`

Atualmente `capturar_dados_mercado()` pode chamar `get_all()` para registro E `get_all_mapped()` para varredura no mesmo ciclo. Mesmo com cache, há overhead de acesso e risco de inconsistência quando `invalidate_cache()` é chamado entre as duas.

**Solução:** Manter um `_inst_map_cache` interno no provider, atualizado apenas quando necessário:

```python
def capturar_dados_mercado(self) -> dict[str, dict]:
    # ...
    if not self._registrado or not self._ativos_registrados:
        instrumentos = self.inst_repo.get_all()
        # Atualiza o cache local do provider
        self._inst_map_cache = {i.cod_put: i for i in instrumentos}
        # ... registro batch ...
    
    # USA o cache local em vez de chamar o repo novamente
    inst_map = self._inst_map_cache
    # ...
```

Isso elimina a dependência do cache de classe do repositório e garante que o mesmo objeto `inst_map` seja usado em todo o ciclo.

---

### SUGESTÃO 4 — Skip de Ciclo Quando `RefreshData` Não Retornou Dados Novos  ⭐⭐ (Impacto Médio)

**Arquivo:** `src/infrastructure/providers/mercado_data_provider.py`

Se `refresh()` retornar dict vazio (sem mudanças), pular o loop de varredura e retornar o `dados_mercado` anterior:

```python
def capturar_dados_mercado(self) -> dict[str, dict]:
    # ...
    mudancas = self.rtd.refresh()
    self._scan_count += 1
    self._ultimo_refresh_timestamp = time.time()

    # Se não houve mudanças E temos dados recentes, reutilizar
    if not mudancas and self._ciclos_sem_dados < 2 and self._ultimo_dados_mercado_cache:
        logger.debug("RTD sem mudanças — reusando cache do ciclo anterior.")
        return self._ultimo_dados_mercado_cache

    # ... varredura normal ...
    self._ultimo_dados_mercado_cache = dados_mercado
    return dados_mercado
```

> **Cuidado:** Manter um contador de ciclos máximo sem refresh real (ex: 3 ciclos = 7,5s) para não deixar dados completamente stale em mercado em movimento.

---

### SUGESTÃO 5 — Limpeza Periódica de `mpp_snapshot`  ⭐⭐ (Impacto Médio — DB I/O)

**Arquivo:** `src/infrastructure/persistence/database.py` ou `mpp_use_case.py`

A tabela `mpp_snapshot` acumula indefinidamente (11.329 rows hoje). Adicionar limpeza automática no início de cada sessão ou a cada N horas:

```python
def limpar_snapshots_antigos(db_path=None, manter_horas: int = 24):
    """Remove snapshots com mais de X horas, mantendo os recentes."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "DELETE FROM mpp_snapshot WHERE timestamp < datetime('now', ? || ' hours')",
            (f"-{manter_horas}",)
        )
        conn.execute("DELETE FROM mpp_historico_distorcoes WHERE created_at < datetime('now', '-7 days')")
        conn.execute("DELETE FROM mpp_spread_history WHERE created_at < datetime('now', '-3 days')")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    finally:
        conn.close()
```

Chamar em `bootstrap.py` no startup e no `MonitorWorker` a cada ~60 minutos.

---

### SUGESTÃO 6 — Mudar `synchronous` de FULL para NORMAL  ⭐ (Impacto Baixo — Fácil)

**Arquivo:** `src/infrastructure/persistence/database.py`

```python
def get_connection(db_path=None) -> sqlite3.Connection:
    # ...
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")   # era FULL (2) — OK com WAL
    conn.execute("PRAGMA cache_size=-8000")     # era -2000 (~8KB) — aumentar para ~8MB
    conn.execute("PRAGMA temp_store=MEMORY")    # operações temporárias em RAM
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

Com WAL + `synchronous=NORMAL`, o banco é durável (sobrevive crash do processo). Apenas crash de OS pode corromper, e o WAL se recupera automaticamente. `cache_size=-8000` (8MB) é adequado para os ~35k instrumentos frequentemente lidos.

---

### SUGESTÃO 7 — Índice em `instrumentos_base(cod_put)`  ⭐ (Impacto Baixo — Fácil)

**Arquivo:** `src/infrastructure/persistence/database.py` — `SCHEMA`

O acesso mais frequente ao banco é por `cod_put` (chave do `inst_map`). Hoje não há índice nessa coluna:

```sql
-- Adicionar ao SCHEMA
CREATE INDEX IF NOT EXISTS idx_instrumentos_cod_put ON instrumentos_base(cod_put);
CREATE INDEX IF NOT EXISTS idx_instrumentos_cod_call ON instrumentos_base(cod_call);
```

E como migração para bancos existentes, adicionar em `init_db()`:

```python
conn.execute("CREATE INDEX IF NOT EXISTS idx_instrumentos_cod_put ON instrumentos_base(cod_put)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_instrumentos_cod_call ON instrumentos_base(cod_call)")
```

Embora o Python use dict para acesso O(1), quando `get_all()` carrega as 35k linhas inicialmente, um índice compound `(cod_put, vencimento)` pode acelerar queries futuras de filtragem.

---

### SUGESTÃO 8 — Desacoplar Onda 2 de `capturar_dados_mercado()`  ⭐ (Impacto Baixo — Organização)

**Arquivo:** `src/infrastructure/providers/mercado_data_provider.py`

Hoje o registro Onda 2 (`_registrar_detalhes_completos`) ocorre dentro do loop principal de varredura, limitado por `MAX_REG_ONDA2_PER_CYCLE = 500`. Isso mistura duas responsabilidades no mesmo hot path.

**Solução:** Mover toda lógica de Onda 2 para `fazer_manutencao()` (que já existe e é chamada a cada 10 ciclos), e dentro de `capturar_dados_mercado()` apenas **detectar** o book (Onda 1) sem registrar:

```python
# Em capturar_dados_mercado() — apenas detecta
if (cab_put and cab_put > 0) or (cab_call and cab_call > 0):
    self._chaves_com_book.add(key)
    # NÃO registra Onda 2 aqui — fazer_manutencao() fará isso

# Em fazer_manutencao() — registra Onda 2 em batch controlado
for key in list(self._chaves_com_book - self._chaves_detalhes_completos):
    # ... _registrar_detalhes_completos ...
```

Isso torna o Fast scan mais puro: apenas leitura de cache, sem nenhum `ConnectData` no hot path.

---

### SUGESTÃO 9 — Diagnóstico por Etapa no Ciclo  ⭐ (Impacto Zero — Visibilidade)

**Arquivo:** `src/infrastructure/providers/mercado_data_provider.py`

Adicionar timers granulares para identificar exatamente onde o tempo vai em cada ciclo:

```python
def capturar_dados_mercado(self) -> dict[str, dict]:
    t0 = time.perf_counter()
    
    # Fase 1: Registro batch
    t1 = time.perf_counter()
    if not self._registrado:
        self._registrar_batch_inteligente(instrumentos)
    t_registro = time.perf_counter() - t1
    
    # Fase 2: RefreshData
    t2 = time.perf_counter()
    self.rtd.refresh()
    t_refresh = time.perf_counter() - t2
    
    # Fase 3: Loop de varredura
    t3 = time.perf_counter()
    # ... loop ...
    t_varredura = time.perf_counter() - t3
    
    logger.info(
        "Ciclo (%s): registro=%.3fs refresh=%.3fs varredura=%.3fs total=%.3fs [%d instrumentos]",
        "G" if is_global_scan else "F",
        t_registro, t_refresh, t_varredura, time.perf_counter() - t0,
        len(dados_mercado)
    )
```

Com isso será possível confirmar definitivamente qual fase domina o tempo e verificar o efeito das otimizações acima.

---

## 3. Plano de Implementação Sugerido

| Prioridade | Sugestão | Esforço | Risco |
|-----------|----------|---------|-------|
| 1° | Sugestão 9 — Diagnóstico por etapa | Baixo | Zero |
| 2° | Sugestão 6 — `synchronous=NORMAL` + `cache_size` | Baixo | Mínimo |
| 3° | Sugestão 5 — Limpeza `mpp_snapshot` | Baixo | Zero |
| 4° | Sugestão 3 — Eliminar 2ª chamada `get_all_mapped` | Médio | Baixo |
| 5° | Sugestão 4 — Skip ciclo sem mudanças | Médio | Baixo |
| 6° | Sugestão 8 — Desacoplar Onda 2 do hot path | Médio | Médio |
| 7° | Sugestão 2 — `RefreshData` seletivo | Alto | Médio |
| 8° | Sugestão 1 — Watchdog thread com timeout | Alto | Alto (COM threading) |

> Começar pelas sugestões 9, 6 e 5 — são seguras, rápidas de implementar e dão visibilidade imediata para validar as demais.

---

## 4. Contexto: O Que NÃO Mudar

Com base na análise do código e das regras em `AGENTS.md`:

- **Strike é RTD-only** — nunca persistir no SQLite. A lógica em `_ler_instrumento_cache()` que rejeita instrumentos sem `strike_rtd` está correta.
- **`ler_campo_cache()` está correto** — lookup de dict + float() em microsegundos, não é o gargalo.
- **Cache de classe em `InstrumentoRepository`** — funciona bem, mas depende de `invalidate_cache()` ser chamado nos momentos certos. Manter a Sugestão 3 como proteção adicional.
- **`_interval_ms = 2500`** — mínimo de 2s está correto para não saturar o servidor RTD.
- **Lógica de priorização JSON** — boa implementação, manter como está.

---

## 5. Observação Sobre o Ambiente AnyDesk

Uma causa externa que pode amplificar a degradação observada esta semana: o acesso via **AnyDesk** introduz latência adicional na thread COM do Profit quando o rendering do Profit Pro está sendo transmitido. O servidor RTD do Profit Pro roda no mesmo processo do Profit — se o Profit está renderizando/transmitindo mais frames (mercado volátil + AnyDesk), pode haver lock interno que atrasa o `RefreshData`. Testar rodar o SpreadHunter diretamente no computador local (sem AnyDesk) e comparar os tempos é um diagnóstico rápido e gratuito.

---

*Gerado por análise estática do código SpreadHunter v0.1.0 — `mercado_data_provider.py`, `rtd_profit.py`, `monitor_worker.py`, `database.py`, `repositories.py`*
