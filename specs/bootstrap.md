# Bootstrap

Inicialização do banco de dados e serviços na partida da aplicação. Chamado por
`main.py` antes de instanciar a UI. Garante que o banco existe, o schema está
atualizado, os parâmetros default estão populados, o calendário B3 está carregado
e o workspace padrão existe.

## Contrato (Requisitos)

### `bootstrap(db_path=None) -> None`
**Garante:**
1. `init_db(db_path)` — cria/atualiza schema e roda migrações.
2. Fecha a conexão de inicialização (`conn.close()`).
3. `ParametroRepository(db_path).seed_defaults()` — garante parâmetros padrão.
4. `carregar_do_banco(db_path)` — popula calendário B3 com feriados do banco.
5. `WorkspaceService(db_path).garantir_system_default()` — cria workspace padrão se não existir.
6. Se o passo 5 falhar, loga warning e continua (não interrompe bootstrap).
7. Protegido por `if __name__ == "__main__"` para execução direta.

## Dependências Diretas (por import)
| Módulo | Arquivo/Símbolo | Uso |
|---|---|---|
| src.infrastructure.persistence.database | `init_db` | Criação/migração do banco |
| src.infrastructure.persistence.repositories.repositories | `ParametroRepository` | Seed de parâmetros |
| src.infrastructure.persistence.repositories.workspace_repository | `WorkspaceSnapshotRepository` | Importado mas não usado diretamente (usado via `WorkspaceService`) |
| src.domain.services.calendario_b3 | `carregar_do_banco` | Import lazy — popula calendário |
| src.application.services.workspace_service | `WorkspaceService` | Import lazy — garante workspace default |
| logging | — | Import lazy para warning |

**É dependência de:**
- `main.py:9` — `from src.infrastructure.persistence.bootstrap import bootstrap`

## Métricas
| Campo | Valor |
|-------|-------|
| Linhas | 30 |
| Arquivo | `src/infrastructure/persistence/bootstrap.py` |
| Última modificação | 2026-07-10 |

## Notas
- 2026-07-10: última modificação.
- 2026-05-28: refatoração intermediária.
- 2026-05-11: criação do arquivo.
- `WorkspaceSnapshotRepository` é importado no topo mas nunca referenciado no corpo da função — POSSÍVEL IMPORT MORTO (usado apenas por `WorkspaceService` internamente, mas o import direto é desnecessário).
- Ordem dos passos é relevante: `init_db()` deve vir antes de tudo (cria tabelas); `seed_defaults()` popula `parametros_operacionais`; `carregar_do_banco()` só funciona se a tabela `feriados_b3` existe.
- O bootstrap é síncrono e bloqueante — se o banco estiver corrompido, a aplicação não inicia.
