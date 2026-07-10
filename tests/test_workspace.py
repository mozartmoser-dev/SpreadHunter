import os
import sys
from pathlib import Path
import tempfile

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


DB_NAME = "spreadhunter.db"


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Cria um banco SQLite temporário e força o get_db_path a usá-lo."""
    temp_db = tmp_path / DB_NAME

    monkeypatch.setenv("APPDATA", str(tmp_path))
    from src.infrastructure.persistence import database as db_mod

    monkeypatch.setattr(db_mod, "DB_NAME", DB_NAME)
    monkeypatch.setattr(db_mod, "_db_local", type(db_mod._db_local)())

    _ = db_mod.get_connection(temp_db)
    db_mod.init_db(temp_db)

    yield temp_db

    try:
        db_mod._db_local = type(db_mod._db_local)()
    except Exception:
        pass


@pytest.fixture
def limpar_qsettings(qapp, monkeypatch):
    monkeypatch.setenv("SPREADHUNTER_QSETTINGS_ORG", "Spreadhunter")
    monkeypatch.setenv("SPREADHUNTER_QSETTINGS_APP", "DesktopMonitor_Tests")
    from src.application.services.workspace_service import WorkspaceService
    assert WorkspaceService.QSETTINGS_ORG == "Spreadhunter"
    from PySide6.QtCore import QSettings
    qs = QSettings("Spreadhunter", "DesktopMonitor_Tests")
    qs.clear()
    qs.sync()
    yield qs
    qs.clear()
    qs.sync()


@pytest.fixture
def workspace_service(db_path, limpar_qsettings):
    limpar_qsettings.blockSignals(True)

    from src.application.services.workspace_service import WorkspaceService
    svc = WorkspaceService(db_path=db_path)
    yield svc
    svc._snapshot_repo_inst()._reset_cache() if hasattr(svc._snapshot_repo_inst(), "_reset_cache") else None


def test_entity_snapshot_roundtrip():
    from src.domain.entities.workspace_snapshot import WorkspaceSnapshot
    snap = WorkspaceSnapshot(
        id=None,
        nome="Teste",
        created_at=__import__("datetime").datetime.now(),
        is_system=True,
        app_version="Spreadhunter",
        parametros={"x": {"valor": 1.0, "estrategia": "GERAL", "descricao": "teste"}},
        workspace={"colunas_ocultas": ["a", "b"]},
    )
    payload = snap.to_json()
    assert payload["schema_version"] == 1
    assert payload["is_system"] is True
    snap2 = WorkspaceSnapshot.from_json(payload)
    assert snap2.nome == "Teste"
    assert snap2.parametros == snap.parametros
    assert snap2.workspace == snap.workspace
    assert snap2.is_system is True


def test_repository_criar_e_listar(db_path):
    from src.domain.entities.workspace_snapshot import WorkspaceSnapshot
    from src.infrastructure.persistence.repositories.workspace_repository import (
        WorkspaceSnapshotRepository,
    )
    repo = WorkspaceSnapshotRepository(db_path=db_path)

    snap = WorkspaceSnapshot(
        id=None,
        nome="snap1",
        created_at=__import__("datetime").datetime.now(),
        is_system=False,
        app_version="Spreadhunter",
        parametros={"k": {"valor": 0.5, "estrategia": "GERAL", "descricao": ""}},
        workspace={"colunas_ocultas": []},
    )
    snap = repo.criar(snap)
    assert snap.id is not None
    assert snap.id > 0

    lista = repo.listar()
    assert len(lista) == 1
    assert lista[0].nome == "snap1"


def test_repository_apagar_system_recusa(db_path):
    from src.domain.entities.workspace_snapshot import WorkspaceSnapshot
    from src.infrastructure.persistence.repositories.workspace_repository import (
        WorkspaceSnapshotRepository,
    )
    repo = WorkspaceSnapshotRepository(db_path=db_path)
    snap_sys = repo.criar_system_default_se_ausente(
        parametros={}, workspace={}
    )
    assert snap_sys is not None
    assert snap_sys.is_system is True

    apagou = repo.apagar(snap_sys.id)
    assert apagou is False, "Snapshot de sistema não pode ser apagado"

    snap2 = repo.obter(snap_sys.id)
    assert snap2 is not None, "Snapshot de sistema continua existindo"


def test_repository_apagar_usuario_ok(db_path):
    from src.domain.entities.workspace_snapshot import WorkspaceSnapshot
    from src.infrastructure.persistence.repositories.workspace_repository import (
        WorkspaceSnapshotRepository,
    )
    repo = WorkspaceSnapshotRepository(db_path=db_path)
    snap = repo.criar(WorkspaceSnapshot(
        id=None, nome="user_snap",
        created_at=__import__("datetime").datetime.now(),
        is_system=False, app_version="Spreadhunter",
        parametros={}, workspace={},
    ))
    assert repo.apagar(snap.id) is True
    assert repo.obter(snap.id) is None


def test_service_criar_e_restaurar_parametro(db_path, limpar_qsettings):
    from src.application.services.workspace_service import WorkspaceService
    from src.infrastructure.persistence.repositories.repositories import ParametroRepository

    qs = limpar_qsettings
    qs.setValue("colunas_ocultas", ["cod_call"])
    qs.sync()

    p = ParametroRepository(db_path)
    from src.domain.entities.parametro_operacional import ParametroOperacional
    p.save(ParametroOperacional(
        chave="dte_min_colar", valor=10.0,
        estrategia="COLAR", descricao="test",
    ))

    svc = WorkspaceService(db_path=db_path)
    snap = svc.criar_snapshot("setup_inicial")
    assert snap.id is not None

    p2 = ParametroRepository(db_path)
    p2.save(ParametroOperacional(
        chave="dte_min_colar", valor=99.0,
        estrategia="COLAR", descricao="test",
    ))
    qs.setValue("colunas_ocultas", [])
    qs.sync()

    svc.restaurar(snap.id)

    p_final = ParametroRepository(db_path).get_by_chave("dte_min_colar")
    assert p_final is not None
    assert abs(float(p_final.valor) - 10.0) < 1e-9, (
        f"Esperado 10.0 após restore, obtido {p_final.valor}"
    )

    from PySide6.QtCore import QSettings
    qs2 = QSettings("Spreadhunter", "DesktopMonitor_Tests")
    assert qs2.value("colunas_ocultas") == ["cod_call"]


def test_service_garantir_system_default_idempotente(db_path):
    from src.application.services.workspace_service import WorkspaceService
    svc = WorkspaceService(db_path=db_path)
    s1 = svc.garantir_system_default()
    s2 = svc.garantir_system_default()
    assert s1 is not None
    assert s2 is None, "Não deve criar duplicado"
    total = svc._snapshot_repo_inst().listar()
    nomes_systema = [s.nome for s in total if s.is_system]
    assert nomes_systema.count("system_default") == 1


def test_service_exportar_e_importar_roundtrip(db_path, tmp_path):
    from src.application.services.workspace_service import WorkspaceService
    from src.domain.entities.workspace_snapshot import WorkspaceSnapshot
    svc = WorkspaceService(db_path=db_path)
    snap = svc.criar_snapshot("exportavel")
    saida = svc.exportar_arquivo(snap.id, tmp_path / "meu_setup.shwsp")
    assert saida.exists()
    repo = svc._snapshot_repo_inst()
    repo.apagar(snap.id)

    snap_imp = svc.importar_arquivo(saida)
    assert snap_imp.id is not None
    assert snap_imp.nome == "exportavel"
    assert snap_imp.is_system is False


def test_service_importar_renomeia_se_duplicado(db_path, tmp_path):
    from src.application.services.workspace_service import WorkspaceService
    svc = WorkspaceService(db_path=db_path)
    s1 = svc.criar_snapshot("meu")
    arquivo = svc.exportar_arquivo(s1.id, tmp_path / "meu.shwsp")
    s_imp = svc.importar_arquivo(arquivo)
    assert s_imp.nome != "meu"
    assert s_imp.nome.startswith("meu")


def test_qsettings_lista_whitelist_contem_chaves_principais():
    from src.application.services.workspace_service import _QSETTINGS_KEYS_CONHECIDAS
    for chave in [
        "colunas_ocultas",
        "colunas_ocultas_vendidas",
        "colunas_ocultas_coberta",
        "main_table_order",
        "vendidas_table_order",
        "coberta_table_order",
        "colar_table_order",
        "colar_cal_table_order",
        "box_table_order",
        "mpp_table_order",
        "parametros/last_section",
    ]:
        assert chave in _QSETTINGS_KEYS_CONHECIDAS
    assert len(_QSETTINGS_KEYS_CONHECIDAS) == 11
