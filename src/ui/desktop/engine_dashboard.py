import os
import psutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QFrame, QPushButton
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from src.ui.desktop.theme import Palette
from src.application.dtos.dtos import EngineStatsDTO

class StatCard(QFrame):
    def __init__(self, title, value, unit="", color="#00f2ff", tooltip=""):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1e1e2f;
                border: 1px solid #2d2d44;
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        
        title_layout = QHBoxLayout()
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet(f"color: #8888aa; font-size: 8pt; font-weight: bold;")
        title_layout.addWidget(self.lbl_title)
        
        self.btn_info = QPushButton("i")
        self.btn_info.setFixedSize(14, 14)
        self.btn_info.setToolTip(tooltip)
        self.btn_info.setStyleSheet("""
            QPushButton {
                background-color: #2d2d44;
                color: #00f2ff;
                border-radius: 7px;
                font-size: 7pt;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #00f2ff; color: #161625; }
        """)
        title_layout.addWidget(self.btn_info)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        self.lbl_value = QLabel(f"{value} {unit}")
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 14pt; font-weight: bold; font-family: Consolas;")
        layout.addWidget(self.lbl_value)
        
    def update_value(self, value, unit=""):
        self.lbl_value.setText(f"{value} {unit}")

class EngineDashboard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Engine Health & Performance")
        self.setFixedSize(500, 480)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Central Widget com borda arredondada e sombra
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("MainFrame")
        self.main_frame.setStyleSheet("""
            QFrame#MainFrame {
                background-color: #161625;
                border: 2px solid #2d2d44;
                border-radius: 15px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.main_frame)
        
        self.content_layout = QVBoxLayout(self.main_frame)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QHBoxLayout()
        title_lbl = QLabel("SYSTEM ENGINE STATUS")
        title_lbl.setStyleSheet("color: #ffffff; font-size: 12pt; font-weight: bold; letter-spacing: 1px;")
        header.addWidget(title_lbl)
        
        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8888aa;
                font-size: 18pt;
                border: none;
            }
            QPushButton:hover { color: #ff5555; }
        """)
        self.btn_close.clicked.connect(self.accept)
        header.addWidget(self.btn_close)
        self.content_layout.addLayout(header)
        
        # Grid de Stats
        grid_layout = QVBoxLayout()
        
        # Row 1: CPU & RAM
        row1 = QHBoxLayout()
        self.card_cpu = StatCard(
            "CPU Usage", "0", "%", "#00ff88", 
            "Carga de processamento do sistema Spreadhunter dedicada ao monitoramento."
        )
        self.card_ram = StatCard(
            "Memory", "0", "MB", "#00f2ff", 
            "Quantidade de memória RAM utilizada pelo aplicativo neste momento."
        )
        row1.addWidget(self.card_cpu)
        row1.addWidget(self.card_ram)
        grid_layout.addLayout(row1)
        
        # Row 2: Latency & Engine
        row2 = QHBoxLayout()
        self.card_latency = StatCard(
            "Scan Latency", "0", "ms", "#ffff00", 
            "Tempo total gasto para capturar os preços do Profit (via RTD), realizar os "
            "cálculos matemáticos de 52.000 ativos e filtrar as oportunidades."
        )
        self.card_engine = StatCard(
            "Engine Core", "NumPy", "Vec", "#ff00ff", 
            "Motor de processamento matemático de alta performance utilizando vetorização."
        )
        row2.addWidget(self.card_latency)
        row2.addWidget(self.card_engine)
        grid_layout.addLayout(row2)
        
        self.content_layout.addLayout(grid_layout)
        
        # Monitoramento de Ativos
        self.content_layout.addSpacing(10)
        scale_header = QHBoxLayout()
        self.lbl_scale = QLabel("SCALE & TOPIC MANAGEMENT")
        self.lbl_scale.setStyleSheet("color: #8888aa; font-size: 8pt; font-weight: bold;")
        scale_header.addWidget(self.lbl_scale)
        
        self.btn_info_scale = QPushButton("i")
        self.btn_info_scale.setFixedSize(14, 14)
        self.btn_info_scale.setToolTip(
            "Onda 1 (Radar): O sistema vigia milhares de ativos perguntando apenas se há movimento.\n"
            "Onda 2 (Foco): Quando o radar detecta movimento, o sistema foca no ativo e traz os preços reais."
        )
        self.btn_info_scale.setStyleSheet("""
            QPushButton {
                background-color: #2d2d44; color: #00f2ff; border-radius: 7px;
                font-size: 7pt; font-weight: bold; border: none;
            }
            QPushButton:hover { background-color: #00f2ff; color: #161625; }
        """)
        scale_header.addWidget(self.btn_info_scale)
        scale_header.addStretch()
        self.content_layout.addLayout(scale_header)
        
        # Barra de Progresso da Carga
        self.progress_load = QProgressBar()
        self.progress_load.setToolTip("Progresso da Carga Onda 1 (Sensores)")
        self.progress_load.setStyleSheet("""
            QProgressBar {
                background-color: #1e1e2f;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                height: 12px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00f2ff, stop:1 #00ff88);
                border-radius: 3px;
            }
        """)
        self.content_layout.addWidget(self.progress_load)
        
        self.lbl_stats_detail = QLabel("Loading instruments...")
        self.lbl_stats_detail.setStyleSheet("color: #aaaaaa; font-size: 9pt; font-family: Consolas;")
        self.content_layout.addWidget(self.lbl_stats_detail)
        
        # Footer Explanatory
        self.content_layout.addStretch()
        footer_lbl = QLabel(
            "O motor utiliza vetorização paralela. Ativos sem liquidez\n"
            "são monitorados via sensores leves para máxima eficiência."
        )
        footer_lbl.setStyleSheet("color: #666688; font-size: 8pt; font-style: italic;")
        footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(footer_lbl)

    def update_stats(self, stats: EngineStatsDTO):
        # Atualiza o balão com o número real de ativos
        msg_latency = (
            f"Tempo total gasto para capturar os preços do Profit (via RTD), realizar os "
            f"cálculos matemáticos de {stats.total_instrumentos:,} ativos e filtrar as oportunidades."
        ).replace(",", ".") # Padrão BR
        self.card_latency.btn_info.setToolTip(msg_latency)
        
        self.card_cpu.update_value(f"{stats.cpu_pct:.1f}", "%")
        self.card_ram.update_value(f"{int(stats.mem_mb)}", "MB")
        self.card_latency.update_value(f"{stats.scan_time_ms}", "ms")
        
        self.progress_load.setMaximum(stats.total_instrumentos)
        self.progress_load.setValue(stats.progresso_idx)
        
        pct_progresso = (stats.progresso_idx / stats.total_instrumentos * 100) if stats.total_instrumentos > 0 else 0
        pct_monitored = (stats.monitored_onda1 / stats.total_instrumentos * 100) if stats.total_instrumentos > 0 else 0
        
        if stats.progresso_idx >= stats.total_instrumentos:
            status_text = "Carga Concluída"
            self.progress_load.setStyleSheet(self.progress_load.styleSheet().replace(
                "stop:0 #00f2ff, stop:1 #00ff88",
                "stop:0 #00ff88, stop:1 #00ff88",
            ))
        elif stats.registrado:
            status_text = "Background Scan"
        else:
            status_text = "Onda 1 (Prioritários)"
        
        detail = (
            f"Database: {stats.total_instrumentos} | "
            f"Sensors: {stats.monitored_onda1} ({pct_monitored:.1f}% kept)\n"
            f"Registrados: {stats.progresso_idx} ({pct_progresso:.1f}%) | Status: {status_text}"
        )
        self.lbl_stats_detail.setText(detail)
        
        # Cor da latência baseada na performance
        if stats.scan_time_ms < 500:
            self.card_latency.lbl_value.setStyleSheet("color: #00ff88; font-size: 14pt; font-weight: bold; font-family: Consolas;")
        elif stats.scan_time_ms < 2000:
            self.card_latency.lbl_value.setStyleSheet("color: #ffff00; font-size: 14pt; font-weight: bold; font-family: Consolas;")
        else:
            self.card_latency.lbl_value.setStyleSheet("color: #ff5555; font-size: 14pt; font-weight: bold; font-family: Consolas;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

