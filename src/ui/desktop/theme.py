DARK_THEME_QSS = """
/* ── Global ──────────────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Segoe UI Semibold", "Inter", sans-serif;
    font-size: 10pt;
}

QWidget:disabled {
    color: #5a5a6e;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {
    background-color: #2d2d44;
    color: #e0e0e0;
    border: 1px solid #3d3d5c;
    border-radius: 5px;
    padding: 7px 18px;
    font-weight: bold;
    font-size: 9pt;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #3d3d5c;
    border-color: #5a5a8a;
}

QPushButton:pressed {
    background-color: #4a4a6a;
}

QPushButton:disabled {
    background-color: #1e1e30;
    color: #4a4a5e;
    border-color: #2a2a3e;
}

QPushButton[class="primary"] {
    background-color: #0f3460;
    border-color: #1654a0;
    color: #ffffff;
}

QPushButton[class="primary"]:hover {
    background-color: #1654a0;
}

QPushButton[class="danger"] {
    background-color: #8b1a1a;
    border-color: #c0392b;
    color: #ffffff;
}

QPushButton[class="danger"]:hover {
    background-color: #a93226;
}

QPushButton[class="success"] {
    background-color: #1a6b3c;
    border-color: #27ae60;
    color: #ffffff;
}

QPushButton[class="success"]:hover {
    background-color: #27ae60;
}

QPushButton[class="monitor-active"] {
    background-color: #c0392b;
    border-color: #e74c3c;
    color: #ffffff;
}

QPushButton[class="monitor-active"]:hover {
    background-color: #e74c3c;
}

/* ── Toolbar ─────────────────────────────────────────────────────── */
QToolBar {
    background-color: #16213e;
    border: none;
    border-bottom: 1px solid #2d2d44;
    spacing: 8px;
    padding: 4px 8px;
}

QToolBar QToolButton {
    background-color: transparent;
    color: #b0b0c0;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 9pt;
}

QToolBar QToolButton:hover {
    background-color: #2d2d44;
    border-color: #3d3d5c;
    color: #ffffff;
}

QToolBar QToolButton:pressed {
    background-color: #3d3d5c;
}

QToolBar::separator {
    background-color: #2d2d44;
    width: 1px;
    margin: 4px 6px;
}

/* ── Status Bar ──────────────────────────────────────────────────── */
QStatusBar {
    background-color: #0f0f23;
    color: #9090a0;
    border-top: 1px solid #2d2d44;
    font-size: 9pt;
    padding: 2px 8px;
}

QStatusBar QLabel {
    color: #b0b0c0;
    padding: 2px 6px;
}

QStatusBar QLabel[class="status-ok"] {
    color: #2ecc71;
    font-weight: bold;
}

QStatusBar QLabel[class="status-warn"] {
    color: #f39c12;
    font-weight: bold;
}

QStatusBar QLabel[class="status-err"] {
    color: #e74c3c;
    font-weight: bold;
}

/* ── Table View ──────────────────────────────────────────────────── */
QTableView {
    background-color: #1a1a2e;
    alternate-background-color: #1e1e34;
    color: #d0d0e0;
    gridline-color: #2a2a3e;
    border: 1px solid #2d2d44;
    border-radius: 4px;
    selection-background-color: #2d4a7a;
    selection-color: #ffffff;
    font-family: "JetBrains Mono", "Consolas", "Courier New", monospace;
    font-size: 9pt;
    outline: none;
}

QTableView::item {
    padding: 4px 8px;
    border-bottom: 1px solid #22223a;
}

QTableView::item:selected {
    background-color: #2d4a7a;
}

QTableView::item:hover {
    background-color: #24243e;
}

QHeaderView::section {
    background-color: #0f0f23;
    color: #a0a0c0;
    border: none;
    border-right: 1px solid #1a1a2e;
    border-bottom: 1px solid #2d2d44;
    padding: 8px 10px;
    font-weight: bold;
    font-size: 8.5pt;
    font-family: "Segoe UI", sans-serif;
    text-transform: uppercase;
}

QHeaderView::section:hover {
    background-color: #1a1a2e;
    color: #ffffff;
}

/* ── Group Box ───────────────────────────────────────────────────── */
QGroupBox {
    background-color: #16213e;
    border: 1px solid #25253d;
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    font-size: 9.5pt;
    color: #00f2ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    color: #ffffff;
    background-color: #1a1a2e;
    border-radius: 4px;
    border: 1px solid #25253d;
}

/* ── Form Layout Labels ─────────────────────────────────────────── */
QFormLayout QLabel {
    color: #9090b0;
    font-size: 9pt;
}

/* ── Line Edit ───────────────────────────────────────────────────── */
QLineEdit {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #2d2d44;
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: #2d4a7a;
}

QLineEdit:focus {
    border-color: #5a5a8a;
}

/* ── Combo Box ───────────────────────────────────────────────────── */
QComboBox {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #2d2d44;
    border-radius: 4px;
    padding: 5px 10px;
    min-height: 22px;
}

QComboBox:hover {
    border-color: #5a5a8a;
}

QComboBox::drop-down {
    border: none;
    background-color: #2d2d44;
    border-radius: 2px;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #9090b0;
    margin-right: 6px;
}

QComboBox QAbstractItemView {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #2d2d44;
    selection-background-color: #2d4a7a;
    outline: none;
}

/* ── Spin Box ────────────────────────────────────────────────────── */
QDoubleSpinBox, QSpinBox {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #2d2d44;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}

QDoubleSpinBox:focus, QSpinBox:focus {
    border-color: #5a5a8a;
}

QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {
    background-color: #2d2d44;
    border: none;
    width: 20px;
}

QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
    background-color: #3d3d5c;
}

/* ── Progress Bar ────────────────────────────────────────────────── */
QProgressBar {
    background-color: #16213e;
    border: 1px solid #2d2d44;
    border-radius: 4px;
    text-align: center;
    color: #e0e0e0;
    min-height: 18px;
}

QProgressBar::chunk {
    background-color: #0f3460;
    border-radius: 3px;
}

/* ── Scroll Area ─────────────────────────────────────────────────── */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #1a1a2e;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #3d3d5c;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #5a5a8a;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1a1a2e;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #3d3d5c;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #5a5a8a;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Message Box ─────────────────────────────────────────────────── */
QMessageBox {
    background-color: #1a1a2e;
}

QMessageBox QLabel {
    color: #e0e0e0;
    font-size: 10pt;
}

/* ── Tab Widget ──────────────────────────────────────────────────── */
QTabWidget::pane {
    background-color: #1e1e34;
    border: 1px solid #2d2d44;
    border-radius: 6px;
    top: -1px;
}

QTabBar::tab {
    background-color: #0f0f23;
    color: #80809b;
    border: 1px solid #2d2d44;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    margin-right: 4px;
    font-weight: bold;
}

QTabBar::tab:selected {
    background-color: #1e1e34;
    color: #00f2ff;
    border-bottom: 2px solid #00f2ff;
}

QTabBar::tab:hover {
    background-color: #16213e;
    color: #ffffff;
}

/* ── Tool Tip ────────────────────────────────────────────────────── */
QToolTip {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #3d3d5c;
    padding: 4px 8px;
    font-size: 9pt;
}

/* ── Menu ────────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #0f0f23;
    color: #b0b0c0;
    border-bottom: 1px solid #2d2d44;
}

QMenuBar::item:selected {
    background-color: #2d2d44;
}

QMenu {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #2d2d44;
}

QMenu::item:selected {
    background-color: #2d4a7a;
}
"""


# ── Cores semanticas do tema (para uso programatico) ────────────────────

class Palette:
    BG_DARK = "#0f0f23"
    BG_BASE = "#1a1a2e"
    BG_RAISED = "#1e1e34"
    BG_SURFACE = "#16213e"
    BG_HOVER = "#2d2d44"

    BORDER = "#2d2d44"
    BORDER_FOCUS = "#5a5a8a"

    TEXT_PRIMARY = "#e0e0e0"
    TEXT_SECONDARY = "#9090b0"
    TEXT_MUTED = "#5a5a6e"

    ACCENT_BLUE = "#2d4a7a"
    ACCENT_BLUE_BRIGHT = "#4a90d9"

    GREEN = "#2ecc71"
    GREEN_DIM = "#1a6b3c"
    RED = "#e74c3c"
    RED_DIM = "#8b1a1a"
    ORANGE = "#f39c12"
    YELLOW = "#f1c40f"
    CYAN = "#1abc9c"
    PURPLE = "#9b59b6"

    ROW_BOX = "#1a2e1a"
    ROW_SBTH = "#1a1a2e"
    ROW_BOXSBTH = "#1a2e2e"
    ROW_NOT_VIABLE = "#2e1a1a"
    ROW_LEILAO = "#3a1a1a"

    LIQ_POSITIVE = "#2ecc71"
    LIQ_NEGATIVE = "#e74c3c"

    STRIKEOUT_COLOR = "#4a4a5e"
