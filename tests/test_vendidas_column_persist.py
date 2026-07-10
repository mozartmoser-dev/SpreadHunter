from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import QApplication, QTableView, QHeaderView

from src.ui.desktop.column_utils import salvar_ordem_colunas, restaurar_ordem_colunas
from src.ui.desktop.monitor_table_model import MonitorTableModel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def test_vendidas_save_restore_order(qapp):
    """Vendidas table — arraste coluna → salvar no Registry → restaurar em nova table."""
    KEY = "vendidas_table_order"
    from src.ui.desktop.vendidas_table_model import VendidasTableModel

    # Simular tabela Vendidas: criar um header com as mesmas colunas
    table = QTableView()
    table.setModel(VendidasTableModel())
    header = table.horizontalHeader()
    header.setSectionsMovable(True)
    header.setDragEnabled(True)

    # Default: 25 colunas (0..24)
    assert header.count() == 25

    header.moveSection(header.visualIndex(4), 0)
    salvar_ordem_colunas(header, KEY)

    table2 = QTableView()
    table2.setModel(VendidasTableModel())
    header2 = table2.horizontalHeader()
    header2.setSectionsMovable(True)
    header2.setDragEnabled(True)
    restaurar_ordem_colunas(header2, KEY)
    saved = [header2.logicalIndex(v) for v in range(header2.count())]
    assert saved[0] == 4, f"Esperado coluna 4 '8 primeira, obtido {saved}"


def test_coberta_save_restore_order(qapp):
    """Coberta table — idem."""
    KEY = "coberta_table_order"
    from src.ui.desktop.venda_coberta_table_model import VendaCobertaTableModel
    table = QTableView()
    table.setModel(VendaCobertaTableModel())
    header = table.horizontalHeader()
    header.setSectionsMovable(True)
    header.setDragEnabled(True)
    assert header.count() == 25

    header.moveSection(header.visualIndex(3), 0)
    salvar_ordem_colunas(header, KEY)

    table2 = QTableView()
    table2.setModel(VendaCobertaTableModel())
    header2 = table2.horizontalHeader()
    header2.setSectionsMovable(True)
    header2.setDragEnabled(True)
    restaurar_ordem_colunas(header2, KEY)
    saved = [header2.logicalIndex(v) for v in range(header2.count())]
    assert saved[0] == 3


def test_main_window_import_nao_quebra(qapp):
    """Importar MainWindow não deve crashar."""
    try:
        from src.ui.desktop.main_window import MainWindow
        assert MainWindow is not None
    except Exception as e:
        pytest.fail(f"MainWindow import crash: {e}")