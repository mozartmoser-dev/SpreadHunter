from PySide6.QtCore import QSettings
import hashlib


def _settings() -> QSettings:
    return QSettings("Spreadhunter", "DesktopMonitor")


def _checksum_colunas(colunas: list[tuple[str, str]]) -> str:
    raw = "|".join(f"{h}:{k}" for h, k in colunas)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def salvar_ordem_colunas(header, key: str, colunas: list[tuple[str, str]] | None = None):
    try:
        order = []
        for v in range(header.count()):
            order.append(header.logicalIndex(v))
        s = _settings()
        s.setValue(key, order)
        if colunas is not None:
            s.setValue(key + "_cksum", _checksum_colunas(colunas))
        s.sync()
    except Exception:
        pass


def _ordem_invalida(header, order_key: str, colunas: list[tuple[str, str]] | None) -> bool:
    if colunas is None:
        return False
    s = _settings()
    saved_checksum = s.value(order_key + "_cksum")
    if not saved_checksum or not isinstance(saved_checksum, str):
        return True
    return saved_checksum != _checksum_colunas(colunas)


def restaurar_ordem_colunas(header, key: str, colunas: list[tuple[str, str]] | None = None):
    try:
        if _ordem_invalida(header, key, colunas):
            s = _settings()
            s.remove(key)
            s.remove(key + "_cksum")
            return
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
    except Exception:
        pass


def salvar_largura_colunas(header, key: str):
    try:
        widths = []
        for i in range(header.count()):
            widths.append(int(header.sectionSize(i)))
        s = _settings()
        s.setValue(key, widths)
        s.sync()
    except Exception:
        pass


def restaurar_largura_colunas(header, key: str):
    try:
        raw = _settings().value(key)
        if not raw or not isinstance(raw, list):
            return
        widths = [int(x) for x in raw]
        n = header.count()
        for i, w in enumerate(widths):
            if i < n and w > 0:
                header.resizeSection(i, w)
    except Exception:
        pass


def contar_colunas_snapshot(key: str) -> int:
    try:
        raw = _settings().value(key)
        if not raw or not isinstance(raw, list):
            return 0
        return len([int(x) for x in raw])
    except Exception:
        return 0


_CHAVES_ORDEM_COLUNAS = (
    "main_table_order",
    "vendidas_table_order",
    "coberta_table_order",
    "colar_table_order",
    "colar_cal_table_order",
    "box_table_order",
    "mpp_table_order",
)


def detectar_incompatibilidade(workspace_snapshot: dict) -> dict[str, tuple[int, int]]:
    """Compara chaves *_order no snapshot vs QSettings atual.

    Retorna dict {chave: (n_snapshot, n_atual)} para chaves incompatíveis.
    Se vazio, não há incompatibilidade.
    """
    diffs: dict[str, tuple[int, int]] = {}
    for key in _CHAVES_ORDEM_COLUNAS:
        snap_val = workspace_snapshot.get(key)
        if not isinstance(snap_val, list) or not snap_val:
            continue
        n_snap = len(snap_val)
        n_atual = contar_colunas_snapshot(key)
        if n_atual > 0 and n_snap != n_atual:
            diffs[key] = (n_snap, n_atual)
    return diffs


def limpar_colunas_incompativeis(header, order_key: str, width_key: str) -> bool:
    """Remove chaves QSettings de ordem/largura se incompatíveis com nº atual.

    Retorna True se limpou (chaves removidas).
    """
    n = header.count()
    if n <= 0:
        return False
    removed = False
    s = _settings()
    for key in (order_key, width_key):
        raw = s.value(key)
        if isinstance(raw, list) and len(raw) != n:
            try:
                s.remove(key)
                removed = True
            except Exception:
                pass
    return removed


def limpar_e_restaurar_colunas(header, order_key: str, width_key: str, colunas: list | None = None) -> None:
    """Limpa QSettings incompatíveis e então restaura ordem/largura.

    Atalho p/ usar nos diálogos: substitui o par restaurar_ordem + restaurar_largura.
    Garante que nunca aplica ordem/largura salva com tamanho diferente do atual.
    """
    limpar_colunas_incompativeis(header, order_key, width_key)
    restaurar_ordem_colunas(header, order_key, colunas)
    restaurar_largura_colunas(header, width_key)
