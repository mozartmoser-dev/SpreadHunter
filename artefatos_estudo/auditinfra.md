# 🛠️ AuditInfra — Auditoria de Infraestrutura, Performance e Bugs: SpreadHunter

> **Perfil do analista:** Desenvolvedor Sênior / Arquiteto de Sistemas (Python & Concorrência)  
> **Data:** 29/05/2026 | **Versão:** 1.0  
> **Escopo:** Análise técnica estrutural do codebase, focando em corretude lógica, bugs ocultos, concorrência, vazamento de recursos e otimização de performance.

---

## 📌 Resumo Executivo

O SpreadHunter é um sistema bem estruturado, que adota princípios de Clean Architecture (separação de responsabilidade entre Domain, Application, Infrastructure e UI). O uso de vetorização (`numpy`) em partes críticas demonstra preocupação com escala.

Contudo, a última refatoração introduziu **um bug impeditivo (de quebra imediata de execução)** e há gargalos significativos de concorrência e I/O que comprometem a estabilidade em ambientes de produção com mais de 50.000 opções cadastradas. Este documento detalha esses problemas e propõe soluções de engenharia limpas e de baixo impacto técnico.

---

## 🔴 1. Bugs Lógicos e Funcionais Críticos

### 1.1. Omissão de Métodos de Processamento em `MonitorWorker`
*   **Arquivo:** [`monitor_worker.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/ui/desktop/monitor_worker.py) (Linhas 90-105)
*   **Problema:** A última alteração substituiu a lógica sequencial do método `run()` por chamadas estruturadas:
    ```python
    self._processar_monitor_geral(rtd)
    self._processar_colares(rtd)
    self._processar_colar_calendario(rtd)
    self._processar_box_4p(rtd)
    self._emitir_estatisticas_engine(t_start_cycle)
    ```
    No entanto, **essas funções não foram declaradas na classe `MonitorWorker`**. A execução dessa thread causará um erro imediato de `AttributeError` assim que o monitor for iniciado, travando toda a aplicação.
*   **Impacto:** Quebra total do funcionamento em produção (bloqueia o scanner).
*   **Solução:** Implementar ou restaurar os corpos desses métodos na classe `MonitorWorker` utilizando a lógica que foi movida do corpo da `run`.

---

### 1.2. Parâmetro Órfão `calendario_strike_diff_pct`
*   **Arquivo:** [`monitor_colares_calendario.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/application/use_cases/monitor_colares_calendario.py) (Linhas 38-51, 180) e [`colar_calendario_dialog.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/ui/desktop/colar_calendario_dialog.py) (Linha 483)
*   **Problema:** O banco de dados e a interface operacional (`ParametrosWidget`) possuem o parâmetro `calendario_strike_diff_pct` para regular a tolerância de strikes na montagem de colares calendário. 
    Contudo:
    1. A UI do diálogo (`ColarCalendarioDialog`) envia apenas parâmetros de DTE e taxa CDI mínima no método `_get_dte_params()`.
    2. O caso de uso `MonitorColaresCalendarioUseCase` tenta ler:
       ```python
       strike_diff_max = preco_ativo * params.get("calendario_strike_diff_pct", 0.03)
       ```
    3. Como o parâmetro nunca é carregado do banco de dados neste fluxo, o sistema sempre utiliza o valor hardcoded de `0.03`. Qualquer ajuste feito pelo usuário na tela de configurações é silenciosamente ignorado.
*   **Impacto:** Usuário perde o controle sobre a tolerância de strikes da estratégia.
*   **Solução:** No caso de uso ou no worker, ler o valor correspondente usando `self.param_repo.get_by_chave("calendario_strike_diff_pct")` e injetá-lo na chamada de `varrer()`.

---

### 1.3. Dessincronização de Estado (Auto-Scan) no Diálogo de Collar Calendário
*   **Arquivo:** [`colar_calendario_dialog.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/ui/desktop/colar_calendario_dialog.py) (Linhas 390-398)
*   **Problema:** O método `_restart_scan_if_auto()` reage a mudanças na seleção de ativos ou parâmetros do formulário. Ele é implementado da seguinte forma:
    ```python
    def _restart_scan_if_auto(self):
        if self._auto_mode:
            self._auto_mode = False  # <--- Desliga o auto_mode na UI
            self._scanning = False
            self.parar_scan_signal.emit()
            selecionados = [...]
            self.iniciar_scan_signal.emit(selecionados, self._get_dte_params())
    ```
    Isso força a UI a desligar o estado de auto-scan (`self._auto_mode = False`), porém emite `iniciar_scan_signal.emit()`, que ativa a varredura automática no worker. A interface visual fica exibindo "Scanner parado" ou em estado manual, enquanto a thread em background continua processando ciclicamente.
*   **Impacto:** Inconsistência de UI/UX e processamento redundante invisível.
*   **Solução:** Não desligar o `_auto_mode` em alterações automáticas; apenas reiniciar a emissão do sinal sem resetar a flag visual de loop da UI.

---

## ⚡ 2. Gargalos de Performance e Latência

### 2.1. Carga Repetitiva de 52k Linhas de Instrumentos no SQLite
*   **Arquivo:** [`mercado_data_provider.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/infrastructure/providers/mercado_data_provider.py) (Linha 241)
*   **Problema:** Toda vez que `capturar_dados_mercado()` é executado com a flag `self._registrado = False` (o que ocorre na inicialização e sempre que os parâmetros operacionais são recarregados), o sistema faz uma leitura total no banco:
    ```python
    instrumentos = self.inst_repo.get_all()  # Lê 52k+ linhas em cada reconfiguração
    ```
    Essa operação custa caro em termos de CPU e I/O de disco.
*   **Impacto:** UI congela momentaneamente durante a recarga de parâmetros e consome muita memória.
*   **Solução:** Utilizar cache em memória compartilhada nos repositórios para que leituras repetidas de dados estáticos evitem requisições I/O brutas no banco SQLite. Como a base de instrumentos só muda após um download (`ImportFlash` ou importação de Excel), a lista estática deve ser cacheada no nível da aplicação e atualizada sob demanda via eventos.

---

### 2.2. Latência de Chamadas COM Síncronas (Gargalo no RTD)
*   **Arquivo:** [`rtd_profit.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/infrastructure/providers/rtd_profit.py) (Linhas 158-184) e [`mercado_data_provider.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/infrastructure/providers/mercado_data_provider.py) (Linha 284)
*   **Problema:** Se um ativo não estiver no cache em tempo real, `MercadoDataProvider` chama:
    ```python
    preco_ativo = self.rtd.ler_campo(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
    ```
    O método `ler_campo` faz uma chamada COM síncrona `self._rtd.ConnectData(...)` diretamente para a API do Profit. Chamadas COM síncronas bloqueiam o fluxo da thread do Python aguardando a resposta da aplicação externa. 
*   **Impacto:** Se o Profit atrasar a resposta de um ticker inativo, a varredura inteira da thread do monitor é congelada, aumentando o ciclo médio de atualização de 2.5s para vários segundos.
*   **Solução:** Proibir chamadas síncronas (`ler_campo`) no laço interno de varredura. Toda leitura deve ser assíncrona baseada apenas no cache atualizado periodicamente por chamadas em lote (usando o mecanismo `RefreshData` que já é performático). Se o dado não está no cache, registra o interesse e aguarda o próximo ciclo.

---

### 2.3. Varredura com Complexidade $O(N^2)$ em Python Puro nas Estratégias
*   **Arquivo:** [`monitor_box.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/application/use_cases/monitor_box.py) (Linhas 105-130) e [`monitor_colares.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/application/use_cases/monitor_colares.py) (Linhas 125-159)
*   **Problema:** Ambas estratégias usam dois loops aninhados (`for i in range... for j in range(i + 1)...`) em Python puro para cruzar cada opção de Put com cada opção de Call para o mesmo ativo e vencimento.
    Se um ativo como PETR4 tiver 300 opções disponíveis para um mesmo vencimento, o loop executará $\frac{300 \times 299}{2} \approx 44.850$ iterações em Python puro.
*   **Impacto:** Desperdício de tempo de CPU no thread de background. Enquanto a calculadora principal de BOX/SBTH foi vetorizada no `CalculadoraVetorizada`, as estratégias de Colar e Box 4P continuam em laços quadráticos lentos em Python puro.
*   **Solução:** 
    1. **Vetorização com Numpy:** Transpor as listas de `members` para arrays e efetuar filtros matriciais (ex.: distância de strikes, viaabilidade financeira) usando operações vetorizadas do Numpy.
    2. **Filtro de Strike Prévio:** Limitar a combinação de Puts e Calls a um "Z-Score" ou range máximo ao redor do preço Spot do ativo *antes* de rodar o loop aninhado. Não faz sentido lógico combinar uma Put com strike R$ 10,00 com uma Call de strike R$ 80,00 em um ativo cotado a R$ 30,00.

---

## 🏛️ 3. Design de Arquitetura e Engenharia de Software

### 3.1. Conexões SQLite Efêmeras (Ausência de Pool ou Singleton de Conexão)
*   **Arquivo:** [`database.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/infrastructure/persistence/database.py) (Linha 11)
*   **Problema:** Toda execução de consulta ou escrita abre e fecha uma conexão com o arquivo SQLite:
    ```python
    def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    ```
    Embora o modo `WAL` ajude a evitar travamentos em acessos concorrentes, o custo de handshake de arquivos de banco em loops de alta frequência no worker é prejudicial.
*   **Impacto:** Desperdício de recursos do sistema operacional e latência de disco desnecessária.
*   **Solução:** Criar um gerenciador de conexões thread-safe ou utilizar uma única conexão reutilizada (Thread-Local) para a thread do worker e outra para a UI.

---

### 3.2. Gerenciamento do COM Threading no PyQt5
*   **Arquivo:** [`monitor_worker.py`](file:///c:/Users/Mozart/Projetos/Spreadhunter/src/ui/desktop/monitor_worker.py) (Linha 59-70)
*   **Problema:** A thread inicializa o COM usando:
    ```python
    import pythoncom
    pythoncom.CoInitialize()
    ```
    Isto funciona, mas não define explicitamente o modelo de concorrência. O ideal para integração com o Profit (ActiveX/COM) é forçar o modelo de apartamento de thread único (Single-Threaded Apartment - STA), garantindo que as chamadas não conflitem com outras bibliotecas ou threads secundárias do Qt.
*   **Solução:** Substituir por `pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)` e cercar o encerramento com blocos `try/finally` estritos para evitar o travamento de instâncias ocultas do Profit no Gerenciador de Tarefas do Windows quando o SpreadHunter é fechado abruptamente.

---

## 📋 4. Plano de Ação Recomendado (Fases)

### Fase 1: Correção de Erros de Lógica (Imediato)
1. **Implementar os métodos ausentes em `MonitorWorker`** trazendo a lógica que estava inline na `run()` de volta para métodos separados.
2. Injetar o parâmetro `calendario_strike_diff_pct` na chamada do caso de uso de Collar Calendário.
3. Consertar a flag `self._auto_mode` em `colar_calendario_dialog.py` para não quebrar a lógica visual do botão de scanner.

### Fase 2: Otimizações de I/O e Banco de Dados (Curto Prazo)
1. Adicionar cache de leitura permanente em `InstrumentoRepository` para a lista completa de opções. Invalidar apenas sob comando explícito (após carga de base).
2. Adotar padrão de conexão compartilhada (ou gerenciada) por thread para evitar `sqlite3.connect` recorrente a cada milissegundo.

### Fase 3: Vetorização e Performance (Médio Prazo)
1. Migrar a lógica quadrática de `MonitorColaresUseCase` e `MonitorBoxUseCase` para operações em matrizes Numpy.
2. Remover chamadas síncronas `rtd.ler_campo` do loop interno do `MercadoDataProvider` e trabalhar exclusivamente em cima do fluxo de cache assíncrono.
