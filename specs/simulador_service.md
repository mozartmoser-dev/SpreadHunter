# SimuladorService

## Propósito

Ponte entre o monitor de operações e o simulador de Gregas (Streamlit). Exporta os dados
de uma operação selecionada para um arquivo JSON e lança o script `scripts/simulador_gregas.py`
como app Streamlit em processo separado, abrindo o navegador em `http://localhost:8501`.

**Papel real no sistema (descoberto via grep, 07/08/2026):** o `exportar_para_simulador()`
é uma função standalone (não é classe) chamada exclusivamente pelo `ColarCalendarioDialog`
(`colar_calendario_dialog.py:1820`). A chamada é feita via lazy import dentro de um método
do diálogo, acionada por botão "Simular Gregas" na UI de detalhes do Collar Calendário.

O serviço é thin — orquestra 3 passos simples: serializar JSON, spawnar subprocesso,
abrir navegador. Não há lógica de negócio, validação de dados ou tratamento de erros
além de `logger.error()`.

## Contrato (Requisitos)

### `exportar_para_simulador(dados_operacao: dict) -> None`

**Garante:**
1. Determina o diretório raiz do projeto como 4 níveis acima de `simulador_service.py`
   (`Path(__file__).resolve().parent.parent.parent.parent`).
2. Serializa `dados_operacao` para `{root}/cenario_atual.json` com `indent=4` e encoding UTF-8.
   Sobrescreve o arquivo se já existir.
3. Verifica se `{root}/scripts/simulador_gregas.py` existe. Se não, loga erro e retorna
   sem fazer mais nada.
4. Lança `subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(script_path)])`
   com `cwd=root`.
5. No Windows (`os.name == "nt"`), usa `creationflags=subprocess.CREATE_NO_WINDOW` para
   evitar janela de console visível.
6. Se o subprocesso falhar (exceção), loga erro e retorna.
7. **Sempre** chama `webbrowser.open("http://localhost:8501")` após o `subprocess.Popen`,
   mesmo que o subprocesso tenha falhado (a exceção é capturada e logada, mas o fluxo
   continua para `webbrowser.open`).
8. POSSÍVEL BUG — `webbrowser.open` é chamado incondicionalmente. Se o script não existe
   (`return` após `logger.error`), o navegador não abre. Mas se o subprocesso lança
   exceção, o `except` captura, loga, e o fluxo continua para `webbrowser.open`, abrindo
   o navegador para um Streamlit que não está rodando. Comportamento inconsistente.

### Constantes de módulo

- `SIMULADOR_SCRIPT = "scripts/simulador_gregas.py"` — caminho relativo ao root.
- `CENARIO_JSON = "cenario_atual.json"` — arquivo de saída no root.
- Porta `8501` — hardcoded no `webbrowser.open()`. Se o Streamlit já estiver rodando
  em outra porta ou se a porta 8501 estiver ocupada, o navegador abre no lugar errado.
  POSSÍVEL BUG — a porta não é configurável e não há mecanismo de detecção de porta
  real do Streamlit.

## Decisões Tomadas

### 1. Função standalone em vez de classe

**Porquê:** O serviço não tem estado — cada chamada é independente. Uma função é mais
simples e evita a indireção de instanciar uma classe para uma operação de 3 passos.
O módulo segue o padrão de "script runner" comum em ferramentas desktop.

### 2. Caminho do root via `Path(__file__).resolve().parent.parent.parent.parent`

**Porquê:** O serviço está em `src/application/services/`. Subir 4 níveis chega ao
diretório raiz do projeto onde `scripts/` e `cenario_atual.json` residem. Esta
abordagem funciona tanto no ambiente de desenvolvimento quanto no executável PyInstaller
(desde que `scripts/simulador_gregas.py` seja incluído no bundle ou esteja acessível).

**Trade-off:** Se a estrutura de diretórios mudar (ex: `services/` for movido),
o cálculo de 4 níveis quebra silenciosamente — o arquivo JSON é escrito em lugar
errado e o script não é encontrado.

### 3. `subprocess.Popen` fire-and-forget (sem `.wait()` ou `.communicate()`)

**Porquê:** O Streamlit é um servidor web de longa duração — bloquear a thread da UI
com `.wait()` congelaria o desktop. O `Popen` dispara o processo e retorna imediatamente,
permitindo que a UI continue responsiva.

**Trade-off:** Não há gerenciamento do ciclo de vida do processo Streamlit:
- Se o usuário clicar "Simular Gregas" múltiplas vezes, múltiplos processos Streamlit
  são spawnados, disputando a porta 8501 (o segundo e seguintes falham com "Address
  already in use").
- Não há cleanup ao fechar o desktop (processos órfãos).
- Não há indicação na UI se o Streamlit está rodando ou não.

### 4. `webbrowser.open()` com URL fixa e porta fixa

**Porquê:** Simplicidade — o Streamlit default é `localhost:8501`. Em 99% dos casos
do usuário, esta porta está livre e o Streamlit sobe nela.

**Trade-off:** Se a porta 8501 estiver ocupada, o Streamlit escolhe outra porta
automaticamente, mas o navegador abre na 8501 (errada). O usuário precisa manualmente
corrigir a porta no navegador ou matar o processo ocupante.

### 5. `CREATE_NO_WINDOW` no Windows

**Porquê:** Evita que uma janela de console preta (cmd.exe) apareça junto com o app
desktop quando o Streamlit é lançado. O Streamlit já tem sua própria interface web;
o console seria apenas ruído visual.

## Decisões Rejeitadas

### 1. Usar `QProcess` em vez de `subprocess.Popen`

Rejeitado porque o `simulador_service.py` é um serviço de aplicação (camada 2), não
um componente de UI. Usar `QProcess` criaria dependência de `PySide6` em uma camada
que deveria ser independente de framework UI. O diálogo chamador (`ColarCalendarioDialog`)
já está na camada UI e poderia gerenciar o `QProcess`, mas isso acoplaria lógica de
subprocesso ao diálogo.

### 2. Matar processo Streamlit anterior ao spawnar novo

Rejeitado por complexidade — exigiria rastrear o PID do processo anterior e implementar
cleanup cross-platform. O custo de implementação não se justificou frente à raridade
de cliques duplos no botão "Simular Gregas".

### 3. Parametrizar porta e caminhos via banco de dados

Rejeitado porque são constantes de infraestrutura, não parâmetros de negócio. A porta
8501 é o default do Streamlit; o caminho do script é fixo na estrutura do projeto.

## Dependências

- `json`, `logging`, `os`, `subprocess`, `sys`, `webbrowser`, `pathlib.Path` — stdlib
- **Não depende de:** entidades de domínio, repositórios, banco de dados, PySide6, RTD/OpenFAST
- **Dependência externa em runtime:** `streamlit` (deve estar instalado no ambiente Python)

**É dependência de:**
- `src/ui/desktop/colar_calendario_dialog.py` (lazy import, único chamador)

## Cobertura de Teste

**Status: 0 testes.**

O módulo não possui testes unitários. É exercitado apenas manualmente via botão
"Simular Gregas" no `ColarCalendarioDialog`.

**Lacunas conhecidas (não cobertas):**
- Caminho do script inexistente — 0 testes
- Subprocesso com falha — 0 testes
- `dados_operacao` vazio ou malformado — 0 testes
- Concorrência (múltiplos cliques no botão) — 0 testes
- Porta 8501 ocupada — 0 testes
- Comportamento em PyInstaller (.exe) — 0 testes
- `cenario_atual.json` já existe e está sendo lido pelo Streamlit anterior — 0 testes
