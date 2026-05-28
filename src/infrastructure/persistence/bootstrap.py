from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import ParametroRepository


def bootstrap(db_path=None) -> None:
    conn = init_db(db_path)
    conn.close()

    repo = ParametroRepository(db_path)
    repo.seed_defaults()

    from src.domain.services.calendario_b3 import carregar_do_banco
    carregar_do_banco(db_path)


if __name__ == "__main__":
    bootstrap()
    print("SpreadHunter DB inicializado com sucesso.")
