import sys
import pytest

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QTableView, QHeaderView

from src.ui.desktop.column_utils import (
    salvar_ordem_colunas,
    restaurar_ordem_colunas,
    salvar_largura_colunas,
    restaurar_largura_colunas,
    limpar_colunas_incompativeis,
    limpar_e_restaurar_colunas,
    detectar_incompatibilidade,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def test_salvar_restaurar_ordem_roundtrip(qapp):
    """Column order save/restore round-trip must preserve custom order."""
    from PySide6.QtCore import QAbstractTableModel

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 5

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()
    header.setSectionsMovable(True)
    header.setDragEnabled(True)

    # Default order: 0,1,2,3,4
    KEY = "test_col_order"

    # Move column 4 -> visual position 0
    header.moveSection(header.visualIndex(4), 0)
    salvar_ordem_colunas(header, KEY)

    # Create fresh header and restore
    table2 = QTableView()
    table2.setModel(TestModel())
    header2 = table2.horizontalHeader()
    header2.setSectionsMovable(True)
    header2.setDragEnabled(True)

    restaurar_ordem_colunas(header2, KEY)

    saved = [header2.logicalIndex(v) for v in range(header2.count())]
    assert saved == [4, 0, 1, 2, 3], f"Expected reordered columns, got {saved}"


def test_salvar_com_qsettings_cleanup(qapp):
    """salvar_ordem_colunas must not raise even with invalid header."""
    class FakeHeader:
        def count(self): return 0
    salvar_ordem_colunas(FakeHeader(), "fake_key")


def test_restaurar_com_logical_invalido_nao_crash(qapp):
    """restaurar_ordem_colunas must skip invalid logical indices gracefully."""
    from PySide6.QtCore import QAbstractTableModel, QSettings

    QSettings("Spreadhunter", "DesktopMonitor").setValue("test_bad_order", [99, -1, 0])

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 3

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()
    header.setSectionsMovable(True)
    header.setDragEnabled(True)

    restaurar_ordem_colunas(header, "test_bad_order")
    # Must not crash; invalid indices 99/-1 are skipped, valid index 0 is moved to v=2
    result = [header.logicalIndex(v) for v in range(header.count())]
    assert len(result) == 3
    assert 0 in result  # valid logical preserved


def test_colar_model_atualizar_chama_begin_end_reset(qapp):
    """atualizar must wrap item replacement in beginResetModel/endResetModel."""
    from src.ui.desktop.colar_dialog import ColarTableModel

    model = ColarTableModel([{"ativo": "PETR4"}])
    assert model.rowCount() == 1

    reset_started = False
    reset_ended = False

    def on_about():
        nonlocal reset_started
        reset_started = True

    def on_reset():
        nonlocal reset_ended
        reset_ended = True

    model.modelAboutToBeReset.connect(on_about)
    model.modelReset.connect(on_reset)

    model.atualizar([{"ativo": "VALE3"}])
    assert reset_started, "beginResetModel must have been called"
    assert reset_ended, "endResetModel must have been called"
    assert model.rowCount() == 1
    assert model._items[0]["ativo"] == "VALE3"


def test_atualizar_resultados_header_freeze_restore(qapp):
    """atualizar_resultados must restore header movable/blocked state after update."""
    from src.ui.desktop.colar_dialog import ColarDialog

    dialog = ColarDialog(db_path=None)
    header = dialog.table_view.horizontalHeader()

    assert header.sectionsMovable() is True
    assert header.signalsBlocked() is False

    dialog.atualizar_resultados([])

    assert header.sectionsMovable() is True
    assert header.signalsBlocked() is False


def test_sectionmoved_com_timer_nao_crash(qapp):
    """sectionMoved via QTimer.singleShot(0) must not crash on rapid column reorder."""
    from PySide6.QtCore import QAbstractTableModel

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 4

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()
    header.setSectionsMovable(True)
    header.setDragEnabled(True)
    header.setSectionsClickable(True)

    # Simulate the same pattern: connect via QTimer.singleShot
    KEY = "test_timer_order"
    header.sectionMoved.connect(
        lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(header, KEY))
    )

    # Simulate several column moves (trigger sectionMoved each time)
    header.moveSection(header.visualIndex(3), 0)
    QApplication.processEvents()

    header.moveSection(header.visualIndex(1), 2)
    QApplication.processEvents()

    header.moveSection(header.visualIndex(0), 3)
    QApplication.processEvents()

    # Must not crash and saved order must exist
    from PySide6.QtCore import QSettings
    saved = QSettings("Spreadhunter", "DesktopMonitor").value(KEY)
    assert saved is not None, "Column order must have been saved"


def test_salvar_restaurar_largura_roundtrip(qapp):
    """Column width save/restore round-trip must preserve custom widths."""
    from PySide6.QtCore import QAbstractTableModel, QSettings

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 4

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()

    KEY = "test_width_roundtrip"
    header.resizeSection(0, 120)
    header.resizeSection(1, 200)
    header.resizeSection(2, 80)
    header.resizeSection(3, 150)
    salvar_largura_colunas(header, KEY)

    saved_raw = QSettings("Spreadhunter", "DesktopMonitor").value(KEY)
    saved = [int(x) for x in saved_raw]
    assert saved == [120, 200, 80, 150]

    table2 = QTableView()
    table2.setModel(TestModel())
    header2 = table2.horizontalHeader()
    header2.resizeSection(0, 50)
    header2.resizeSection(1, 50)
    header2.resizeSection(2, 50)
    header2.resizeSection(3, 50)
    restaurar_largura_colunas(header2, KEY)

    assert header2.sectionSize(0) == 120
    assert header2.sectionSize(1) == 200
    assert header2.sectionSize(2) == 80
    assert header2.sectionSize(3) == 150


def test_restaurar_largura_com_mais_colunas_snapshot(qapp):
    """Quando snapshot tem mais larguras que o header atual, aplica só as que cabem."""
    from PySide6.QtCore import QAbstractTableModel, QSettings

    QSettings("Spreadhunter", "DesktopMonitor").setValue("test_width_extra", [100, 200, 300, 400, 500])

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 3

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()
    restaurar_largura_colunas(header, "test_width_extra")
    assert header.sectionSize(0) == 100
    assert header.sectionSize(1) == 200
    assert header.sectionSize(2) == 300


def test_restaurar_largura_com_menos_colunas_snapshot(qapp):
    """Quando snapshot tem menos larguras que o header atual, colunas extras mantêm default."""
    from PySide6.QtCore import QAbstractTableModel, QSettings

    QSettings("Spreadhunter", "DesktopMonitor").setValue("test_width_menor", [100, 200])

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 4

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()
    default_width = header.sectionSize(2)
    restaurar_largura_colunas(header, "test_width_menor")
    assert header.sectionSize(0) == 100
    assert header.sectionSize(1) == 200
    assert header.sectionSize(2) == default_width  # não há no snapshot
    assert header.sectionSize(3) == default_width


def test_limpar_colunas_incompativeis_quando_mais_colunas(qapp):
    """limpar_colunas_incompativeis deve remover QSettings se nº de colunas bate não."""
    from PySide6.QtCore import QAbstractTableModel, QSettings

    qs = QSettings("Spreadhunter", "DesktopMonitor")
    KEY_O = "test_limpar_order"
    KEY_W = "test_limpar_width"
    qs.setValue(KEY_O, [0, 1, 2, 3, 4])  # 5 colunas no snapshot
    qs.setValue(KEY_W, [100, 200, 300, 400, 500])

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 3  # 3 no header (incompatível)

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()
    removed = limpar_colunas_incompativeis(header, KEY_O, KEY_W)
    assert removed is True
    assert qs.value(KEY_O) is None
    assert qs.value(KEY_W) is None


def test_limpar_colunas_incompativeis_quando_compativel_nao_atualiza(qapp):
    """limpar_colunas_incompativeis não deve remover se nº bater."""
    from PySide6.QtCore import QAbstractTableModel, QSettings

    qs = QSettings("Spreadhunter", "DesktopMonitor")
    KEY_O = "test_ok_order"
    KEY_W = "test_ok_width"
    qs.setValue(KEY_O, [0, 1, 2])
    qs.setValue(KEY_W, [100, 200, 300])

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 3

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()
    removed = limpar_colunas_incompativeis(header, KEY_O, KEY_W)
    assert removed is False
    assert [int(x) for x in qs.value(KEY_O)] == [0, 1, 2]
    assert [int(x) for x in qs.value(KEY_W)] == [100, 200, 300]


def test_limpar_e_restaurar_colunas_aplica_se_compativel(qapp):
    """limpar_e_restaurar_colunas não destrói configuração válida."""
    from PySide6.QtCore import QAbstractTableModel, QSettings

    qs = QSettings("Spreadhunter", "DesktopMonitor")
    KEY_O = "test_combo_order"
    KEY_W = "test_combo_width"
    qs.setValue(KEY_O, [2, 0, 1])
    qs.setValue(KEY_W, [150, 90, 200])

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 3

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()
    header.setSectionsMovable(True)
    header.setDragEnabled(True)
    limpar_e_restaurar_colunas(header, KEY_O, KEY_W)
    assert [header.logicalIndex(v) for v in range(header.count())] == [2, 0, 1]
    assert header.sectionSize(0) == 150
    assert header.sectionSize(1) == 90
    assert header.sectionSize(2) == 200


def test_limpar_e_restaurar_colunas_descarta_se_incompativel(qapp):
    """limpar_e_restaurar_colunas descarta snapshot incompatível sem aplicar ordem/lixo."""
    from PySide6.QtCore import QAbstractTableModel, QSettings

    qs = QSettings("Spreadhunter", "DesktopMonitor")
    KEY_O = "test_combo_bad_order"
    KEY_W = "test_combo_bad_width"
    qs.setValue(KEY_O, [3, 1, 2, 0, 4])  # 5 colunas
    qs.setValue(KEY_W, [10, 20, 30, 40, 50])

    class TestModel(QAbstractTableModel):
        def rowCount(self, parent=None): return 0
        def columnCount(self, parent=None): return 3  # incompatível

    table = QTableView()
    table.setModel(TestModel())
    header = table.horizontalHeader()
    header.setSectionsMovable(True)
    header.setDragEnabled(True)
    limpar_e_restaurar_colunas(header, KEY_O, KEY_W)
    assert qs.value(KEY_O) is None
    assert qs.value(KEY_W) is None
    assert [header.logicalIndex(v) for v in range(header.count())] == [0, 1, 2]


def test_detectar_incompatibilidade_retorna_diffs(qapp):
    """detectar_incompatibilidade retorna dict {chave: (snap, atual)}."""
    from PySide6.QtCore import QSettings

    qs = QSettings("Spreadhunter", "DesktopMonitor")
    qs.setValue("main_table_order", [0, 1, 2, 3])  # 4
    qs.setValue("colar_table_order", [0, 1])     # 2

    # Snapshot com 5 colunas em main e 2 em colar
    snap = {
        "main_table_order": [4, 0, 1, 2, 3],   # n_snap=5 vs atual=4 → diff
        "colar_table_order": [0, 1],            # n_snap=2 vs atual=2 → ok
    }
    diffs = detectar_incompatibilidade(snap)
    assert "main_table_order" in diffs
    assert diffs["main_table_order"] == (5, 4)
    assert "colar_table_order" not in diffs


def test_detectar_incompatibilidade_sem_snapshot_atual(qapp):
    """Se QSettings atual está vazio, não há incompatibilidade."""
    from PySide6.QtCore import QSettings

    QSettings("Spreadhunter", "DesktopMonitor").remove("colar_table_order")
    snap = {"colar_table_order": [0, 1, 2]}
    diffs = detectar_incompatibilidade(snap)
    assert diffs == {}
