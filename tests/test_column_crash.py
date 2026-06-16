import sys
import pytest

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QTableView, QHeaderView

from src.ui.desktop.column_utils import salvar_ordem_colunas, restaurar_ordem_colunas


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
