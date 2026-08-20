import time
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableView,
    QAbstractItemView, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QThread, Signal
from PySide6.QtGui import QFont, QColor, QBrush

from src.domain.services.market_data_source import FieldName
from src.ui.desktop.theme import Palette


def consultar_divergencias_strikes(source, db_path, hoje):
    """Consulta o PEX no OpenFast e retorna (itens, resumo).

    Roda em background (QThread) para não travar a UI. Lógica equivalente à
    antiga consulta síncrona que dormia 2s na thread da interface.
    """
    import time as _time
    from src.infrastructure.persistence.database import get_connection

    conn = get_connection(db_path)
    proventos = conn.execute(
        "SELECT ativo, valor FROM dividendos WHERE data_ex = ? AND valor > 0",
        (hoje,),
    ).fetchall()
    provento_por_ativo = {}
    for a, v in proventos:
        provento_por_ativo[a] = provento_por_ativo.get(a, 0.0) + float(v)
    ativos = sorted(set(provento_por_ativo))

    if not ativos:
        return [], "Nenhum ativo com data_ex hoje. Nada a ajustar."

    itens: list[dict] = []
    codigos = []
    pares = []
    for ativo in ativos:
        insts = conn.execute(
            "SELECT cod_put, cod_call, strike FROM instrumentos_base WHERE ativo = ? AND strike IS NOT NULL",
            (ativo,),
        ).fetchall()
        for cp, cc, st in insts:
            if cp:
                codigos.append((cp, FieldName.STRIKE))
            if cc:
                codigos.append((cc, FieldName.STRIKE))
            pares.append((ativo, cp, cc, st, provento_por_ativo.get(ativo, 0.0)))

    if not codigos:
        return [], "Nenhum instrumento no banco para os ativos com data_ex hoje."

    source.registrar_lista(codigos)
    _time.sleep(2.0)

    for ativo, cp, cc, st, provento in pares:
        pex_put = source.ler_campos(cp, FieldName.STRIKE, allow_stale=True).get(FieldName.STRIKE) if cp else None
        pex_call = source.ler_campos(cc, FieldName.STRIKE, allow_stale=True).get(FieldName.STRIKE) if cc else None
        pex = pex_put if pex_put else pex_call
        cod = cp or cc
        if pex is None or not st:
            continue
        if abs(float(pex) - float(st)) > 0.005:
            itens.append({
                "ativo": ativo,
                "cod": cod,
                "strike_banco": float(st),
                "strike_openfast": float(pex),
                "provento": provento,
                "data_ex": hoje,
                "esperado": float(st) - float(provento),
            })

    resumo = (
        f"Divergências encontradas: {len(itens)}"
        if itens
        else "Nenhuma divergência entre banco e OpenFast nos ativos com data_ex hoje."
    )
    return itens, resumo


class _ConsultarStrikesThread(QThread):
    concluido = Signal(list, str)
    falhou = Signal(str)

    def __init__(self, source, db_path, hoje):
        super().__init__()
        self._source = source
        self._db_path = db_path
        self._hoje = hoje

    def run(self):
        try:
            itens, resumo = consultar_divergencias_strikes(
                self._source, self._db_path, self._hoje
            )
            self.concluido.emit(itens, resumo)
        except Exception as e:
            self.falhou.emit(str(e))


class AjusteStrikesTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Código", "cod"),
        ("Strike Banco", "strike_banco"),
        ("Strike OpenFast", "strike_openfast"),
        ("Provento", "provento"),
        ("Data EX", "data_ex"),
        ("Esperado", "esperado"),
    ]

    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.COLUMNS):
            if role == Qt.ItemDataRole.DisplayRole:
                return self.COLUMNS[section][0]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key in ("strike_banco", "strike_openfast", "esperado"):
                v = item.get(col_key)
                return "{:.2f}".format(v) if v is not None else "-"
            if col_key == "provento":
                v = item.get(col_key)
                return "{:.4f}".format(v) if v else "-"
            if col_key == "data_ex":
                v = item.get(col_key)
                if v:
                    try:
                        return datetime.fromisoformat(str(v)).strftime("%d/%m/%Y")
                    except ValueError:
                        return str(v)
                return "-"
            return str(item.get(col_key, "-"))

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "strike_banco":
                return QBrush(QColor("#e74c3c"))
            if col_key == "strike_openfast":
                return QBrush(QColor("#2ecc71"))
            if col_key == "ativo":
                return QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
            return QBrush(QColor(Palette.TEXT_PRIMARY))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("strike_banco", "strike_openfast", "provento", "esperado"):
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def atualizar(self, items):
        self.layoutAboutToBeChanged.emit()
        self._items = items
        self.layoutChanged.emit()


class AjusteStrikesDialog(QDialog):
    def __init__(self, db_path, parent=None, divergencias=None):
        super().__init__(parent)
        self.db_path = db_path
        self.divergencias = divergencias or []
        self.aplicou = False
        self._items = []
        self._hoje = None
        self._consultar_thread = None
        self.setWindowTitle("Ajustar Strikes (divergência por provento)")
        self.setMinimumSize(760, 420)
        self._setup_ui()
        self._iniciar_consulta()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.lbl_topo = QLabel("Consultando OpenFast...")
        self.lbl_topo.setStyleSheet("font-size: 9.5pt; color: {};".format(Palette.TEXT_PRIMARY))
        layout.addWidget(self.lbl_topo)

        self.table_view = QTableView()
        self.model = AjusteStrikesTableModel()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.MultiSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setFont(QFont("Consolas", 9))
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.verticalHeader().setDefaultSectionSize(26)
        self.table_view.verticalHeader().hide()
        layout.addWidget(self.table_view, stretch=1)

        btn_layout = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_MUTED))
        btn_layout.addWidget(self.lbl_status)
        btn_layout.addStretch()

        self.btn_selecionar_todos = QPushButton("☑ Selecionar todos")
        self.btn_selecionar_todos.setEnabled(False)
        self.btn_selecionar_todos.clicked.connect(self._selecionar_todos)
        btn_layout.addWidget(self.btn_selecionar_todos)

        self.btn_aplicar = QPushButton("✔ Aplicar selecionados")
        self.btn_aplicar.setProperty("class", "primary")
        self.btn_aplicar.clicked.connect(self._aplicar)
        self.btn_aplicar.setEnabled(False)
        btn_layout.addWidget(self.btn_aplicar)

        self.btn_aplicar_todos = QPushButton("✔✔ Aplicar todos")
        self.btn_aplicar_todos.setEnabled(False)
        self.btn_aplicar_todos.clicked.connect(self._aplicar_todos)
        btn_layout.addWidget(self.btn_aplicar_todos)

        self.btn_ajustar_series = QPushButton("✔✔✔ Ajustar todas as séries (strike − provento)")
        self.btn_ajustar_series.setEnabled(False)
        self.btn_ajustar_series.clicked.connect(self._ajustar_todas_series)
        btn_layout.addWidget(self.btn_ajustar_series)

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def _obter_source(self):
        parent = self.parent()
        if parent is None:
            return None
        worker = getattr(parent, "_worker", None)
        if worker is None:
            return None
        return worker.market_data_source

    def _iniciar_consulta(self):
        """Abre a janela na hora e consulta o PEX em background (sem travar a UI)."""
        from datetime import date
        self._hoje = date.today().isoformat()

        source = self._obter_source()
        if source is None or not getattr(source, "disponivel", False):
            self.lbl_topo.setText("❌ OpenFast desconectado — não é possível consultar os strikes.")
            self.lbl_topo.setStyleSheet("color: {}; font-weight: bold;".format(Palette.RED))
            return

        self.lbl_topo.setText("Consultando PEX no OpenFast... (os dados chegam em instantes)")
        self._consultar_thread = _ConsultarStrikesThread(source, self.db_path, self._hoje)
        self._consultar_thread.concluido.connect(self._on_consulta_concluida)
        self._consultar_thread.falhou.connect(self._on_consulta_falhou)
        self._consultar_thread.start()

    def _on_consulta_concluida(self, itens, resumo):
        self._items = itens
        self.model.atualizar(itens)
        self.lbl_topo.setText(resumo)
        self.lbl_status.setText(f"{len(itens)} registros")
        self.btn_aplicar.setEnabled(bool(itens))
        self.btn_aplicar_todos.setEnabled(bool(itens))
        self.btn_selecionar_todos.setEnabled(bool(itens))
        self.btn_ajustar_series.setEnabled(bool(itens))

    def _on_consulta_falhou(self, msg):
        self.lbl_topo.setText("❌ Erro ao consultar PEX no OpenFast.")
        self.lbl_topo.setStyleSheet("color: {}; font-weight: bold;".format(Palette.RED))
        QMessageBox.critical(self, "Erro", f"Erro ao consultar PEX:\n{msg}")

    def _ajustar_todas_series(self):
        """Aplica strike = strike - provento em TODOS os strikes de todos os ativos
        com data_ex hoje e evidência de divergência (os que aparecem na lista).

        Salvaguardas (NUNCA aplicar às cegas):
        1. Só ativos que já têm divergência constatada na lista (com PEX lido).
        2. Múltiplos proventos no dia (JCP + dividendo) são somados via SUM(valor).
        3. ANTES de aplicar, valida a fórmula contra o PEX de cada par da amostra:
           esperado = strike_banco - provento deve bater com strike_openfast.
           - Se TODOS os pares do ativo conferirem -> aplica a fórmula em todas
             as séries do ativo.
           - Se QUALQUER par divergir -> NÃO aplica no ativo e reporta os códigos.
           - Se o ativo não tiver NENHUM par com PEX na amostra -> não valida,
             NÃO aplica e reporta.
        """
        if not self._items or not self._hoje:
            return

        from src.infrastructure.persistence.database import get_connection
        conn = get_connection(self.db_path)
        ativos = sorted({it["ativo"] for it in self._items})
        proventos = {}
        for a in ativos:
            row = conn.execute(
                "SELECT SUM(valor) FROM dividendos WHERE ativo = ? AND data_ex = ? AND valor > 0",
                (a, self._hoje),
            ).fetchone()
            proventos[a] = float(row[0] or 0.0) if row else 0.0

        ativos_com_provento = [a for a in ativos if proventos[a] > 0]
        if not ativos_com_provento:
            QMessageBox.information(
                self, "Aviso",
                "Nenhum ativo com provento cadastrado para data_ex hoje.",
            )
            return

        # ── Salvaguarda 3: valida a fórmula contra o PEX da amostra ──
        validar: dict[str, dict] = {}
        divergencias_amostra: list[str] = []
        sem_pex: list[str] = []
        for it in self._items:
            d = validar.setdefault(it["ativo"], {"n": 0, "ok": 0, "problemas": []})
            d["n"] += 1
            esperado = round(float(it["strike_banco"]) - float(it["provento"]), 2)
            if abs(esperado - float(it["strike_openfast"])) <= 0.005:
                d["ok"] += 1
            else:
                d["problemas"].append(
                    f"  {it['cod']}: banco={it['strike_banco']:.2f} → esperado={esperado:.2f}, "
                    f"PEX={it['strike_openfast']:.2f}"
                )
        for a in ativos_com_provento:
            v = validar.get(a, {"n": 0, "ok": 0, "problemas": []})
            if v["n"] == 0:
                sem_pex.append(a)
            elif v["ok"] != v["n"]:
                divergencias_amostra.append(a)
                divergencias_amostra.extend(v["problemas"])

        if sem_pex or divergencias_amostra:
            partes = []
            if sem_pex:
                partes.append(
                    "SEM amostra de PEX (não é possível validar, NÃO aplicado):\n  "
                    + ", ".join(sem_pex)
                )
            if divergencias_amostra:
                partes.append(
                    "FÓRMULA NÃO CONFERE com o PEX (NÃO aplicado):\n"
                    + "\n".join(divergencias_amostra)
                )
            QMessageBox.warning(
                self, "Ajuste bloqueado pela validação",
                "\n\n".join(partes) + "\n\n"
                "Use '✔ Aplicar selecionados'/'✔✔ Aplicar todos' (valor do PEX por linha) "
                "para esses casos, ou investigue antes de ajustar.",
            )
            return

        # ── Confirmação com a prova da amostra ──
        n_pend = conn.execute(
            f"SELECT COUNT(*) FROM instrumentos_base "
            f"WHERE ativo IN ({','.join('?' * len(ativos_com_provento))}) "
            f"AND strike_ajustado_em IS NULL",
            ativos_com_provento,
        ).fetchone()[0]
        if n_pend == 0:
            QMessageBox.information(self, "Aviso", "Nenhum strike pendente para ajustar.")
            return

        prova = "\n".join(
            f"  {a}: {validar[a]['ok']}/{validar[a]['n']} pares conferem "
            f"(strike_banco − provento = PEX)"
            for a in ativos_com_provento
        )
        resp = QMessageBox.question(
            self, "Ajustar todas as séries",
            f"Ajustar {n_pend} strike(s) de {', '.join(ativos_com_provento)}?\n\n"
            f"Validação contra PEX (amostra):\n{prova}\n\n"
            "Aplica strike = strike − provento em TODAS as séries, equivalentes ao valor do OpenFast.\n"
            "O opcoes.net corrige em 1-2 dias; a próxima importação substitui pelo valor do site.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source = self._obter_source()
        aplicados = 0
        corretos_pulados = 0
        anomalias: list[str] = []
        for a in ativos_com_provento:
            prov = proventos[a]
            rows = conn.execute(
                "SELECT id, cod_put, cod_call, strike FROM instrumentos_base "
                "WHERE ativo = ? AND strike_ajustado_em IS NULL",
                (a,),
            ).fetchall()
            for rid, cp, cc, strike_banco in rows:
                if not strike_banco:
                    continue
                strike_banco = float(strike_banco)
                pex = None
                for cod in (cp, cc):
                    if cod and source is not None:
                        try:
                            v = source.ler_campos(cod, FieldName.STRIKE, allow_stale=True).get(FieldName.STRIKE)
                            if v is not None:
                                pex = float(v)
                                break
                        except Exception:
                            pass
                if pex is not None:
                    if abs(strike_banco - pex) <= 0.005:
                        corretos_pulados += 1
                        continue
                    if abs((strike_banco - prov) - pex) <= 0.005:
                        novo = pex
                    else:
                        anomalias.append(
                            f"  {cp or cc}: banco={strike_banco:.2f}, PEX={pex:.2f}, "
                            f"esperado={strike_banco - prov:.2f}"
                        )
                        continue
                else:
                    novo = round(strike_banco - prov, 2)
                try:
                    cur = conn.execute(
                        "UPDATE instrumentos_base SET strike = ?, strike_ajustado_em = ? WHERE id = ?",
                        (novo, agora, rid),
                    )
                    aplicados += cur.rowcount
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Erro ao ajustar {cp or cc}:\n{e}")
        conn.commit()

        if anomalias:
            QMessageBox.warning(
                self, "Ajuste parcial com divergências não esperadas",
                "Strikes NÃO ajustados (banco não é pré-ajuste nem igual ao PEX):\n"
                + "\n".join(anomalias)
                + "\n\nInvestigue antes de ajustá-los manualmente.",
            )

        self.aplicou = aplicados > 0
        if self.aplicou:
            QMessageBox.information(
                self, "Concluído",
                f"{aplicados} strike(s) ajustados em todas as séries "
                f"({', '.join(ativos_com_provento)}).\n"
                + (f"{corretos_pulados} já estavam no valor do PEX (ignorados).\n" if corretos_pulados else "")
                + "O opcoes.net corrige em 1-2 dias; a próxima importação substitui pelo valor do site.",
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Aviso", "Nenhum strike foi atualizado.")

    def _selecionar_todos(self):
        self.table_view.selectAll()

    def _aplicar_todos(self):
        if not self._items:
            return
        resp = QMessageBox.question(
            self, "Aplicar todos",
            f"Aplicar o ajuste em TODOS os {len(self._items)} registros?\n\n"
            "O strike do banco será substituído pelo valor do OpenFast.\n"
            "O opcoes.net corrige em 1-2 dias; a próxima importação substitui pelo valor do site.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        self._aplicar(indices=range(len(self._items)))

    def _aplicar(self, indices=None):
        if indices is None:
            indices = {idx.row() for idx in self.table_view.selectionModel().selectedRows()}
            if not indices:
                QMessageBox.information(self, "Aviso", "Selecione ao menos uma linha.")
                return

        from src.infrastructure.persistence.database import get_connection
        conn = get_connection(self.db_path)
        aplicados = 0
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for r in indices:
            item = self._items[r]
            try:
                cur = conn.execute(
                    "UPDATE instrumentos_base SET strike = ?, strike_ajustado_em = ? "
                    "WHERE ativo = ? AND (cod_put = ? OR cod_call = ?)",
                    (item["strike_openfast"], agora, item["ativo"], item["cod"], item["cod"]),
                )
                aplicados += cur.rowcount
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao ajustar {item['cod']}:\n{e}")
        conn.commit()

        self.aplicou = aplicados > 0
        if self.aplicou:
            QMessageBox.information(
                self, "Concluído",
                f"{aplicados} strike(s) ajustado(s) para o valor do OpenFast.\n"
                "O opcoes.net corrige em 1-2 dias; a próxima importação substitui pelo valor do site."
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Aviso", "Nenhuma linha foi atualizada.")