from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.infrastructure.persistence.repositories.workspace_repository import (
    WorkspaceSnapshotRepository,
)


def bootstrap(db_path=None) -> None:
    conn = init_db(db_path)
    conn.close()

    repo = ParametroRepository(db_path)
    repo.seed_defaults()

    from src.domain.services.calendario_b3 import carregar_do_banco
    carregar_do_banco(db_path)

    try:
        from src.application.services.workspace_service import WorkspaceService
        WorkspaceService(db_path=db_path).garantir_system_default()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "Falha ao garantir system_default do workspace: %s", e
        )


if __name__ == "__main__":
    bootstrap()
    print("SpreadHunter DB inicializado com sucesso.")
