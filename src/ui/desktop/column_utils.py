from PyQt5.QtCore import QSettings


def _settings() -> QSettings:
    return QSettings("Spreadhunter", "DesktopMonitor")


def salvar_ordem_colunas(header, key: str):
    order = []
    for v in range(header.count()):
        order.append(header.logicalIndex(v))
    _settings().setValue(key, order)


def restaurar_ordem_colunas(header, key: str):
    raw = _settings().value(key)
    if not raw or not isinstance(raw, list):
        return
    order = [int(x) for x in raw]
    n = header.count()
    for v, logical in enumerate(order):
        if 0 <= logical < n:
            cv = header.visualIndex(logical)
            if cv != v:
                header.moveSection(cv, v)
