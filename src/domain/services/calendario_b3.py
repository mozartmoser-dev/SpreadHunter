from datetime import date

import numpy as np

FERIADOS_B3_PADRAO = [
    "2024-01-01", "2024-02-12", "2024-02-13", "2024-03-29",
    "2024-04-21", "2024-05-01", "2024-05-30", "2024-07-09",
    "2024-09-07", "2024-10-12", "2024-11-02", "2024-11-15",
    "2024-11-20", "2024-12-25", "2025-01-01", "2025-03-04",
    "2025-04-18", "2025-04-21", "2025-05-01", "2025-06-19",
    "2025-09-07", "2025-10-12", "2025-11-02", "2025-11-15",
    "2025-11-20", "2025-12-25", "2026-01-01", "2026-02-16",
    "2026-02-17", "2026-04-03", "2026-04-21", "2026-05-01",
    "2026-06-04", "2026-07-09", "2026-09-07", "2026-10-12",
    "2026-11-02", "2026-11-15", "2026-11-20", "2026-12-25",
]

_feriados_atuais = list(FERIADOS_B3_PADRAO)
_B3_CALENDAR = np.busdaycalendar(holidays=np.array(_feriados_atuais, dtype="datetime64[D]"))
B3_CALENDAR = _B3_CALENDAR


def _reconstruir_calendario():
    global _B3_CALENDAR, B3_CALENDAR
    _B3_CALENDAR = np.busdaycalendar(holidays=np.array(_feriados_atuais, dtype="datetime64[D]"))
    B3_CALENDAR = _B3_CALENDAR


def atualizar_calendario(feriados: list[str]):
    _feriados_atuais.clear()
    _feriados_atuais.extend(sorted(feriados))
    _reconstruir_calendario()


def carregar_do_banco(db_path: str | None = None):
    try:
        from src.infrastructure.persistence.repositories.repositories import FeriadoB3Repository
        repo = FeriadoB3Repository(db_path)
        rows = repo.get_all()
        if rows:
            feriados = sorted(r["data"] for r in rows if r.get("data"))
            if feriados:
                atualizar_calendario(feriados)
    except Exception:
        pass


def dc_to_du_aproximado(dias_corridos: int) -> int:
    if dias_corridos <= 0:
        return 0
    return max(1, int(round(dias_corridos * 252 / 365)))


def dc_to_du_exato(data_inicio: date, data_fim: date) -> int:
    if data_inicio >= data_fim:
        return 0
    return int(np.busday_count(data_inicio, data_fim, busdaycal=_B3_CALENDAR))


def dc_to_du_vetorizado(data_inicio: date, vencimentos: np.ndarray) -> np.ndarray:
    if len(vencimentos) == 0:
        return np.array([], dtype=int)
    datas_fim = np.array(vencimentos, dtype="datetime64[D]")
    datas_ini = np.full(len(vencimentos), np.datetime64(data_inicio, "D"))
    du = np.busday_count(datas_ini, datas_fim, busdaycal=B3_CALENDAR)
    return np.maximum(du, 0)


def dc_to_du(data_inicio: date | None, data_fim: date | None, dias_corridos: int = 0) -> int:
    if data_inicio is not None and data_fim is not None:
        return dc_to_du_exato(data_inicio, data_fim)
    return dc_to_du_aproximado(dias_corridos)


def frac_du(dias_uteis: int) -> float:
    if dias_uteis <= 0:
        return 0.0
    return dias_uteis / 252


def frac_dc(dias_corridos: int) -> float:
    if dias_corridos <= 0:
        return 0.0
    return dias_corridos / 365


def eh_feriado(dt: date) -> bool:
    return dt.isoformat() in _feriados_atuais
