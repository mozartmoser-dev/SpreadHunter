import pytest
from datetime import date

from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
)
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.application.use_cases.mpp_use_case import MPPUseCase


@pytest.fixture
def db_com_instrumentos(tmp_path):
    path = tmp_path / "test_mpp_mapa.db"
    conn = init_db(path)
    conn.close()

    repo = InstrumentoRepository(path)
    for ativo, cod_put, venc in [
        ("PETR4", "PETRF173", date(2027, 1, 17)),
        ("VALE3", "VALEF173", date(2027, 2, 19)),
        ("BBSE3", "BBSEF173", date(2027, 3, 19)),
    ]:
        repo.save(InstrumentoOpcional(
            ativo=ativo,
            cod_put=cod_put,
            cod_call=cod_put.replace("F", "G"),
            vencimento=venc,
            tipo_opcao=TipoOpcao.EUROPEIA,
        ))
    return path


def test_obter_instrumentos_mapa_retorna_todos(db_com_instrumentos):
    mpp = MPPUseCase(db_com_instrumentos)
    mapa = mpp._obter_instrumentos_mapa()

    assert len(mapa) == 3, "Deve retornar UM mapa por cod_put, nao apenas o ultimo"
    assert set(mapa.keys()) == {"PETRF173", "VALEF173", "BBSEF173"}
    assert mapa["PETRF173"]["ativo"] == "PETR4"
    assert mapa["VALEF173"]["ativo"] == "VALE3"
    assert mapa["BBSEF173"]["ativo"] == "BBSE3"


def test_obter_instrumentos_mapa_filtra_por_whitelist(db_com_instrumentos):
    mpp = MPPUseCase(db_com_instrumentos)
    mapa = mpp._obter_instrumentos_mapa(ativos=["PETR4", "VALE3"])

    assert len(mapa) == 2
    assert "PETRF173" in mapa
    assert "VALEF173" in mapa
    assert "BBSEF173" not in mapa
