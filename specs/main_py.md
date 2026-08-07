# main.py

## Propósito

Ponto de entrada da aplicação Spreadhunter. Inicializa logging (arquivo rotativo + console), limpa `__pycache__`, executa `bootstrap()` do banco de dados e lança `QApplication` com `MainWindow` em modo maximizado. Aplicação single-window, single-process.

## Contrato (Requisitos)

### `run_app(db_path=None)`
**Garante:**
1. Remove todos os diretórios `__pycache__` recursivamente antes de iniciar.
2. Chama `bootstrap(db_path)` para inicializar/migrar o banco SQLite.
3. Cria `QApplication` com estilo "Fusion".
4. Instancia `MainWindow(db_path)` e exibe maximizada (`showMaximized()`).
5. Entra no event loop (`app.exec()`) e retorna o exit code via `sys.exit()`.
6. Se `db_path` não for fornecido, `MainWindow` usa `get_db_path()` internamente.

### Configuração de logging (nível módulo)
**Garante:**
1. `RotatingFileHandler` em `logs/spreadhunter.log` (5 MB, 5 backups, UTF-8).
2. `StreamHandler` para console.
3. Log de profiling: `logs/profile_mercado.log` (modo `w` para primeiro handler, `a` para subsequentes).
4. `matplotlib.font_manager` silenciado para WARNING.
5. Filtro `_FiltroManutencao` no handler de profiling que só captura mensagens contendo "Manutenção", "Ciclo:", "_flush_buffer", "Background scan", "Onda 1" ou "Lote Onda 1".

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `logging` | stdlib | Configuração de handlers de log |
| `logging.handlers` | `RotatingFileHandler` | Arquivo de log rotativo |
| `shutil` | stdlib | `rmtree` para limpeza de `__pycache__` |
| `sys` | stdlib | `sys.exit()` |
| `pathlib` | `Path` | Path para arquivos de log |
| `PySide6.QtWidgets` | `QApplication` | Event loop Qt |
| `src.infrastructure.persistence.bootstrap` | `bootstrap` | Inicialização do banco |
| `src.ui.desktop.main_window` | `MainWindow` | Janela principal |

## Métricas

| Linhas | 58 |
| Classes | 1 (`_FiltroManutencao`, interna) |
| Testes | Não (testado indiretamente via testes de UI que importam `MainWindow`) |

## Notas

- **Ponto único de entrada:** `if __name__ == "__main__": run_app()` — sem argumentos de CLI.
- **PyInstaller:** O spec `spreadhunter.spec` referencia este arquivo como entry point. O `_clear_pycache()` é relevante para builds congeladas.
- **Log de profiling:** Três handlers diferentes apontam para o mesmo arquivo (`profile_mercado.log`), o primeiro em modo `w` (sobrescreve), os outros em `a` (append). Isso significa que na inicialização o arquivo é truncado, depois todos os handlers subsequentes fazem append.
- **`load_dotenv()` NÃO é chamado aqui** — é chamado no `opcoesnet_client.py` (import do módulo). Credenciais `.env` são carregadas quando o `OpcoesNetClient` é importado pela primeira vez, não na inicialização global.
