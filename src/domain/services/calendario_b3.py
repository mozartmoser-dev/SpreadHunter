from datetime import date

import numpy as np

FERIADOS_B3 = [
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

_B3_CALENDAR = np.busdaycalendar(holidays=np.array(FERIADOS_B3, dtype="datetime64[D]"))


def dc_to_du_aproximado(dias_corridos: int) -> int:
    if dias_corridos <= 0:
        return 0
    return max(1, int(round(dias_corridos * 252 / 365)))


def dc_to_du_exato(data_inicio: date, data_fim: date) -> int:
    if data_inicio >= data_fim:
        return 0
    return int(np.busday_count(data_inicio, data_fim, busdaycal=_B3_CALENDAR))


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
