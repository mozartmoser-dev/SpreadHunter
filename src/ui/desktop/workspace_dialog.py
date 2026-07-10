from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.application.services.workspace_service import WorkspaceService
from src.domain.entities.workspace_snapshot import WorkspaceSnapshot


class WorkspaceDialog(QDialog):
    restaurar_solicitado = Signal(int)

    def __init__(
        self,
        service: WorkspaceService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workspace — Salvar / Restaurar")
        self.resize(720, 480)
        self._service = service
        self._snapshots: list[WorkspaceSnapshot] = []

        self._setup_style()
        self._setup_ui()
        self._setup_shortcuts()
        self._carregar_lista()

    def _setup_style(self) -> None:
        self.setStyleSheet(
            """
            QDialog { background-color: #0d0d0d; color: #e0e0e0; }
            QListWidget {
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 4px;
            }
            QListWidget::item { padding: 6px; border-radius: 3px; }
            QListWidget::item:selected { background-color: #2d4a7a; color: #ffffff; }
            QListWidget::item:disabled { color: #888; }
            QTextEdit {
                background-color: #1a1a2e;
                color: #cfcfd5;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
            QPushButton {
                background-color: #2d2d44;
                color: #e0e0e0;
                border: 1px solid #3d3d54;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 9pt;
            }
            QPushButton:hover { background-color: #3d3d54; color: #1abc9c; }
            QPushButton:disabled { color: #666; background-color: #1f1f30; }
            QLabel { color: #cfcfd5; font-size: 9pt; }
            """
        )

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        title = QLabel(
            "Snapshots salvos de Parâmetros + Workspace (ordem de colunas).\n"
            "Sistema = restaurável sempre. Restauração é imediata."
        )
        title.setStyleSheet("font-weight: 600; padding: 4px;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal, self)

        self._lista = QListWidget()
        self._lista.itemSelectionChanged.connect(self._on_selecionado)
        splitter.addWidget(self._lista)

        detalhes = QWidget()
        detalhes_layout = QVBoxLayout(detalhes)
        detalhes_layout.setContentsMargins(0, 0, 0, 0)
        self._detalhes = QTextEdit()
        self._detalhes.setReadOnly(True)
        detalhes_layout.addWidget(self._detalhes)
        splitter.addWidget(detalhes)

        splitter.setSizes([260, 460])
        root.addWidget(splitter, 1)

        # Linha de botões de snapshot
        linha1 = QHBoxLayout()
        self._btn_salvar = QPushButton("💾 Salvar Atual...")
        self._btn_salvar.setToolTip("Salvar um snapshot do estado atual (Ctrl+Shift+S)")
        self._btn_salvar.clicked.connect(self._salvar_atual)
        linha1.addWidget(self._btn_salvar)

        self._btn_restaurar = QPushButton("↩️ Restaurar")
        self._btn_restaurar.setToolTip("Restaurar o snapshot selecionado (Ctrl+Shift+R)")
        self._btn_restaurar.clicked.connect(self._restaurar_selecionado)
        linha1.addWidget(self._btn_restaurar)

        self._btn_apagar = QPushButton("🗑️ Apagar")
        self._btn_apagar.setToolTip("Apagar o snapshot selecionado (snapshots de sistema não podem ser apagados)")
        self._btn_apagar.clicked.connect(self._apagar_selecionado)
        linha1.addWidget(self._btn_apagar)
        linha1.addStretch()
        root.addLayout(linha1)

        # Linha de import/export
        linha2 = QHBoxLayout()
        self._btn_exportar = QPushButton("📤 Exportar...")
        self._btn_exportar.setToolTip("Exportar o snapshot selecionado para um arquivo .shwsp")
        self._btn_exportar.clicked.connect(self._exportar_selecionado)
        linha2.addWidget(self._btn_exportar)

        self._btn_importar = QPushButton("📥 Importar...")
        self._btn_importar.setToolTip("Importar um snapshot de um arquivo .shwsp")
        self._btn_importar.clicked.connect(self._importar_arquivo)
        linha2.addWidget(self._btn_importar)

        self._btn_fechar = QPushButton("Fechar")
        self._btn_fechar.clicked.connect(self.accept)
        linha2.addWidget(self._btn_fechar)

        root.addLayout(linha2)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #888; padding: 4px;")
        root.addWidget(self._status)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.ControlModifier | Qt.ShiftModifier | Qt.Key_S), self, self._salvar_atual)
        QShortcut(QKeySequence(Qt.ControlModifier | Qt.ShiftModifier | Qt.Key_R), self, self._restaurar_selecionado)

    # ---------- dados ----------
    def _carregar_lista(self) -> None:
        self._lista.blockSignals(True)
        self._lista.clear()
        try:
            self._snapshots = self._service._snapshot_repo_inst().listar()
        except Exception as e:
            QMessageBox.critical(self, "Workspace", f"Falha ao listar snapshots:\n{e}")
            self._snapshots = []
        for snap in self._snapshots:
            label = ("🛡 " if snap.is_system else "   ") + snap.nome
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, snap.id)
            if snap.is_system:
                f = QFont()
                f.setBold(True)
                item.setFont(f)
                item.setData(Qt.ToolTipRole, "Snapshot de sistema — criado na primeira execução. Não pode ser apagado.")
            self._lista.addItem(item)
        if self._lista.count() > 0:
            self._lista.setCurrentRow(0)
        self._lista.blockSignals(False)
        self._on_selecionado()
        self._status.setText(f"{len(self._snapshots)} snapshot(s) — total.")

    def _snapshot_selecionado(self) -> WorkspaceSnapshot | None:
        item = self._lista.currentItem()
        if item is None:
            return None
        sid = item.data(Qt.UserRole)
        if not isinstance(sid, int):
            return None
        for s in self._snapshots:
            if s.id == sid:
                return s
        return self._service._snapshot_repo_inst().obter(sid)

    def _on_selecionado(self) -> None:
        snap = self._snapshot_selecionado()
        if snap is None:
            self._detalhes.setPlainText("Selecione um snapshot à esquerda para ver detalhes.")
            self._btn_restaurar.setEnabled(False)
            self._btn_apagar.setEnabled(False)
            self._btn_exportar.setEnabled(False)
            return

        self._btn_restaurar.setEnabled(True)
        self._btn_apagar.setEnabled(not snap.is_system)
        self._btn_exportar.setEnabled(True)

        n_param = len(snap.parametros)
        chaves_qs = sorted(snap.workspace.keys())
        linhas = [
            f"Nome:         {snap.nome}",
            f"Tipo:         {'Sistema (não pode ser apagado)' if snap.is_system else 'Usuário'}",
            f"Criado em:    {snap.created_at.strftime('%Y-%m-%d %H:%M:%S') if snap.created_at else '-'}",
            f"App version:  {snap.app_version}",
            "",
            f"Parâmetros:   {n_param} chave(s)",
            f"Workspace:    {len(chaves_qs)} chave(s) QSettings",
            "",
            "Chaves QSettings capturadas:",
        ]
        for k in chaves_qs:
            linhas.append(f"  • {k}")
        if not chaves_qs:
            linhas.append("  (vazio)")
        self._detalhes.setPlainText("\n".join(linhas))

    # ---------- ações ----------
    def _salvar_atual(self) -> None:
        nomes_existentes = [s.nome for s in self._snapshots]
        nome, ok = QInputDialog.getText(
            self,
            "Salvar Snapshot",
            "Nome do snapshot:",
            text="Meu setup",
        )
        if not ok:
            return
        nome = (nome or "").strip()
        if not nome:
            QMessageBox.warning(self, "Workspace", "Nome vazio — operação cancelada.")
            return
        if nome in nomes_existentes:
            resp = QMessageBox.question(
                self,
                "Workspace",
                f"Já existe um snapshot com o nome '{nome}'. Sobrescrever?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
            existing = next(s for s in self._snapshots if s.nome == nome)
            self._service._snapshot_repo_inst().apagar(existing.id)

        try:
            self._service.criar_snapshot(nome)
        except Exception as e:
            QMessageBox.critical(self, "Workspace", f"Falha ao salvar:\n{e}")
            return
        self._status.setText(f"✓ Snapshot '{nome}' salvo.")
        self._carregar_lista()

    def _restaurar_selecionado(self) -> None:
        snap = self._snapshot_selecionado()
        if snap is None:
            return
        if snap.is_system:
            aviso = "Restaurar o snapshot de SISTEMA reverterá TODOS os parâmetros para o estado da primeira execução deste .exe. Continuar?"
        else:
            aviso = f"Restaurar o snapshot '{snap.nome}' sobrescreverá os parâmetros atuais e as chaves de workspace (ordem de colunas). Continuar?"

        resp = QMessageBox.question(
            self,
            "Restaurar Snapshot",
            aviso,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        try:
            self._service.restaurar(snap.id)
        except Exception as e:
            QMessageBox.critical(self, "Workspace", f"Falha ao restaurar:\n{e}")
            return
        self._status.setText(f"✓ Snapshot '{snap.nome}' restaurado. Feche e reabra diálogos para aplicar.")
        QMessageBox.information(
            self,
            "Workspace",
            f"Snapshot '{snap.nome}' restaurado com sucesso.\n\n"
            "Para ver o efeito:\n"
            "• Reabra os diálogos de Colar/Collar Calendário/Box 4P/MPP.\n"
            "• Abra Parâmetros novamente para ver os valores trocados.\n\n"
            "(Snapshots são lidos pelos diálogos na hora de abrir.)",
        )
        self.restaurar_solicitado.emit(snap.id)

    def _apagar_selecionado(self) -> None:
        snap = self._snapshot_selecionado()
        if snap is None:
            return
        if snap.is_system:
            QMessageBox.warning(self, "Workspace", "Snapshots de sistema não podem ser apagados.")
            return
        resp = QMessageBox.question(
            self,
            "Apagar Snapshot",
            f"Apagar o snapshot '{snap.nome}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        try:
            self._service._snapshot_repo_inst().apagar(snap.id)
        except Exception as e:
            QMessageBox.critical(self, "Workspace", f"Falha ao apagar:\n{e}")
            return
        self._status.setText(f"✓ Snapshot '{snap.nome}' apagado.")
        self._carregar_lista()

    def _exportar_selecionado(self) -> None:
        snap = self._snapshot_selecionado()
        if snap is None:
            return
        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Snapshot",
            f"{snap.nome}.shwsp",
            "Workspace Spreadhunter (*.shwsp);;Todos (*.*)",
        )
        if not caminho:
            return
        try:
            self._service.exportar_arquivo(snap.id, Path(caminho))
        except Exception as e:
            QMessageBox.critical(self, "Workspace", f"Falha ao exportar:\n{e}")
            return
        self._status.setText(f"✓ Exportado para {caminho}")

    def _importar_arquivo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Importar Snapshot",
            "",
            "Workspace Spreadhunter (*.shwsp);;JSON (*.json);;Todos (*.*)",
        )
        if not caminho:
            return
        try:
            snap = self._service.importar_arquivo(Path(caminho))
        except Exception as e:
            QMessageBox.critical(self, "Workspace", f"Falha ao importar:\n{e}")
            return
        self._status.setText(f"✓ Importado como '{snap.nome}'.")
        self._carregar_lista()
