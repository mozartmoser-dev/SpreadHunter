"""Quick test: load EstudosCalendarioDialog and print row count."""
import sys, os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
from src.ui.desktop.estudos_calendario_dialog import EstudosCalendarioDialog

dlg = EstudosCalendarioDialog()
print(f'Rows: {dlg.model.rowCount()}')
print(f'Title: {dlg.windowTitle()}')
for i in range(min(6, dlg.model.rowCount())):
    vals = [str(dlg.model.data(dlg.model.index(i, c)) or '') for c in range(5)]
    print(f'  row {i}: {" | ".join(vals)}')
print('OK')
