import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QAbstractItemView,
    QMessageBox, QLabel, QHeaderView, QTextEdit
)
from PyQt5.QtCore import Qt, QAbstractTableModel
from PyQt5.QtGui import QFont, QColor, QBrush

from src.ui.desktop.theme import Palette


class HistoricoTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Data/Hora", "created_at"),
        ("Ativo", "ativo"),
        ("Strike", "strike"),
        ("Operação", "operacao"),
        ("Dias", "dias"),
        ("Preço Ativo", "preco_ativo"),
        ("Custo", "custo"),
        ("Ganho %", "ganho"),
        ("Rent. vs CDI", "cdi_rent"),
    ]

    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and 0 <= section < len(self.COLUMNS):
            if role == Qt.DisplayRole:
                return self.COLUMNS[section][0]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.DisplayRole:
            if col_key == "created_at":
                dt_str = item["created_at"]
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    return dt.strftime("%d/%m/%Y %H:%M:%S")
                except ValueError:
                    return dt_str
            if col_key == "strike":
                return "{:.2f}".format(item["strike"])
            if col_key == "preco_ativo":
                return "{:.2f}".format(item["preco_ativo"])
            if col_key == "custo":
                op = item["operacao"]
                val = item["custo_box"] if op in ("BOX", "BOXSBTH") else item["custo_sbth"]
                return "{:.4f}".format(val) if val is not None else "-"
            if col_key == "ganho":
                op = item["operacao"]
                val = item["pct_ganho_box"] if op in ("BOX", "BOXSBTH") else item["pct_ganho_sbth"]
                return "{:.2f}%".format(val * 100) if val is not None else "-"
            if col_key == "cdi_rent":
                op = item["operacao"]
                val = item["pct_cdi_box"] if op in ("BOX", "BOXSBTH") else item["pct_cdi_sbth"]
                return "{:.2f}x".format(val) if val is not None else "-"
            return str(item.get(col_key, ""))

        if role == Qt.TextAlignmentRole:
            if col_key in ("strike", "operacao", "dias", "preco_ativo", "custo", "ganho", "cdi_rent"):
                return Qt.AlignCenter | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            if col_key == "ganho":
                op = item["operacao"]
                val = item["pct_ganho_box"] if op in ("BOX", "BOXSBTH") else item["pct_ganho_sbth"]
                if val and val > 0:
                    return QBrush(QColor(Palette.LIQ_POSITIVE))
            if col_key == "cdi_rent":
                return QBrush(QColor(Palette.YELLOW))
            if col_key == "operacao":
                op = item["operacao"]
                if op == "BOX":
                    return QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
                elif op == "SBTH":
                    return QBrush(QColor(Palette.CYAN))
                return QBrush(QColor(Palette.PURPLE))
            return QBrush(QColor(Palette.TEXT_PRIMARY))

        return None

    def get_item(self, row: int) -> dict | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def atualizar(self, items):
        self.layoutAboutToBeChanged.emit()
        self._items = items
        self.layoutChanged.emit()


class HistoricoDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Histórico de Operações Registradas")
        self.setMinimumSize(950, 500)
        self._setup_ui()
        self.carregar_dados()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl_title = QLabel("Histórico de Operações Registradas")
        lbl_title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: {}; padding: 4px 0;".format(Palette.TEXT_PRIMARY)
        )
        layout.addWidget(lbl_title)

        self.table_view = QTableView()
        self.model = HistoricoTableModel()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setFont(QFont("Consolas", 9))
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(26)
        self.table_view.verticalHeader().hide()
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table_view, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_detalhes = QPushButton("🔍 Ver Detalhes")
        self.btn_detalhes.setProperty("class", "primary")
        self.btn_detalhes.clicked.connect(self._on_detalhes_clicked)
        btn_layout.addWidget(self.btn_detalhes)

        self.btn_excluir = QPushButton("🗑️ Excluir Registro")
        self.btn_excluir.setProperty("class", "danger")
        self.btn_excluir.clicked.connect(self._on_excluir_clicked)
        btn_layout.addWidget(self.btn_excluir)

        btn_layout.addStretch()

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def carregar_dados(self):
        from src.infrastructure.persistence.repositories.repositories import OportunidadeRepository
        repo = OportunidadeRepository(self.db_path)
        try:
            items = repo.get_historico_completo()
            self.model.atualizar(items)
        except Exception as e:
            QMessageBox.critical(self, "Erro", "Erro ao carregar histórico: " + str(e))

    def _on_row_double_clicked(self, index):
        self._on_detalhes_clicked()

    def _on_detalhes_clicked(self):
        selected = self.table_view.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma operação da tabela.")
            return

        row = selected[0].row()
        item = self.model.get_item(row)
        if not item:
            return

        self._mostrar_detalhes(item)

    def _mostrar_detalhes(self, item):
        snapshot_raw = item.get("snapshot_mercado")
        if isinstance(snapshot_raw, str):
            try:
                snapshot = json.loads(snapshot_raw)
            except Exception:
                snapshot = {}
        else:
            snapshot = snapshot_raw or {}

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Cotações de Registro - {item['ativo']} {item['strike']:.2f}")
        dlg.setMinimumSize(420, 380)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl = QLabel(f"Snapshot de Mercado — {item['ativo']} (Strike: {item['strike']:.2f})")
        lbl.setStyleSheet("font-size: 11pt; font-weight: bold; color: {};".format(Palette.TEXT_PRIMARY))
        layout.addWidget(lbl)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFont(QFont("Consolas", 10))
        txt.setStyleSheet("background-color: #0f0f1a; color: #00ffcc; border: 1px solid #2d2d44; border-radius: 4px;")

        lines = [
            f"Preço Ação: R$ {item['preco_ativo']:.2f}",
            f"Dias p/ Exercício: {item['dias']}",
            f"Estratégia: {item['operacao']}",
            "",
            "=== Dados de Cotação de Opções ==="
        ]

        if snapshot:
            lines.extend([
                f"Opção Tipo: {snapshot.get('tipo_opcao', 'N/A')}",
                f"Compra Put: R$ {snapshot.get('of_compra_put', 0.0):.2f}",
                f"Venda Put: R$ {snapshot.get('of_venda_put', 0.0):.2f}",
                f"Compra Call: R$ {snapshot.get('of_compra_call', 0.0):.2f}",
                f"Venda Call: R$ {snapshot.get('of_venda_call', 0.0):.2f}",
                f"Qul Put: {snapshot.get('qul_put', 0.0):.0f}",
                f"Qul Call: {snapshot.get('qul_call', 0.0):.0f}",
                f"Liq Lote Put: {snapshot.get('liq_put_x_lote', 0.0):.0f}",
                f"Liq Lote Call: {snapshot.get('liq_call_x_lote', 0.0):.0f}",
                f"Leilão Ativo: {'Sim' if snapshot.get('em_leilao', False) else 'Não'}",
            ])

            if "coefic_alvo" in snapshot:
                lines.extend([
                    "",
                    "=== Detalhes Basket ITM ===",
                    f"Custo Alvo (Coef): R$ {snapshot.get('coefic_alvo', 0.0):.4f}",
                    f"Custo Mercado (Coef): R$ {snapshot.get('coefic_mercado', 0.0):.4f}",
                    f"Spread Operação: R$ {snapshot.get('spread', 0.0):.2f}",
                    f"Ganho Alvo Definido: {snapshot.get('taxa_ganho', 0.0):.2f}%"
                ])
        else:
            lines.append("Nenhum dado de cotação adicional salvo.")

        txt.setPlainText("\n".join(lines))
        layout.addWidget(txt, stretch=1)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(dlg.accept)
        layout.addWidget(btn_fechar)

        dlg.exec_()

    def _on_excluir_clicked(self):
        selected = self.table_view.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma operação para excluir.")
            return

        row = selected[0].row()
        item = self.model.get_item(row)
        if not item:
            return

        confirm = QMessageBox.question(
            self, "Confirmação de Exclusão",
            f"Deseja realmente excluir a operação registrada de {item['ativo']} (Strike: {item['strike']:.2f}) de {item['created_at']}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            from src.infrastructure.persistence.repositories.repositories import OportunidadeRepository
            repo = OportunidadeRepository(self.db_path)
            try:
                success = repo.delete_by_id(item["id"])
                if success:
                    QMessageBox.information(self, "Sucesso", "Operação excluída com sucesso.")
                    self.carregar_dados()
                else:
                    QMessageBox.warning(self, "Aviso", "A operação não pôde ser encontrada para exclusão.")
            except Exception as e:
                QMessageBox.critical(self, "Erro", "Erro ao excluir operação: " + str(e))
