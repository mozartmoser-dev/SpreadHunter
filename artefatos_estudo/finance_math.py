import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import Union, List, Optional

# Lista de feriados B3/ANBIMA (Exemplo para 2024/2025)
# Em produção, este dicionário pode ser carregado de um JSON ou via API da ANBIMA
FERIADOS_B3 = [
    '2024-01-01', '2024-01-25', '2024-02-12', '2024-02-13', '2024-03-29',
    '2024-04-21', '2024-05-01', '2024-05-30', '2024-07-09', '2024-11-15',
    '2024-11-20', '2024-12-25', '2025-01-01'
]

# Pré-calcula o calendário para performance (padrão em sistemas de alta frequência)
_B3_CALENDAR = np.busdaycalendar(holidays=np.array(FERIADOS_B3, dtype="datetime64[D]"))

def get_business_days(start_date: Union[str, datetime, date], end_date: Union[str, datetime, date]) -> int:
    """
    Calcula dias úteis (DU) entre duas datas seguindo o calendário da B3.
    """
    try:
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
    except Exception:
        return 0
    
    if start >= end:
        return 0

    try:
        return int(np.busday_count(start, end, busdaycal=_B3_CALENDAR))
    except ValueError:
        return 0

def year_fraction_b3_du(start_date: Union[str, datetime, date], end_date: Union[str, datetime, date]) -> float:
    """
    Retorna a fração do ano no padrão B3 (DU/252).
    INDICADO PARA: Black-Scholes, Gregas (Theta, Vega) e Taxa DI.
    """
    return get_business_days(start_date, end_date) / 252.0

def normalize_volatility(vol_365: float) -> float:
    """
    Converte a volatilidade da base 365 (internacional) para 252 (B3).
    Fórmula: sigma_252 = sigma_365 * sqrt(365/252)
    """
    return vol_365 * np.sqrt(365.0 / 252.0)

def year_fraction_dc(start_date: Union[str, datetime, date], end_date: Union[str, datetime, date]) -> float:
    """
    Retorna a fração do ano em dias corridos (DC/365).
    INDICADO PARA: Visualização humana e contagem de tempo linear.
    """
    try:
        s, e = pd.to_datetime(start_date), pd.to_datetime(end_date)
        dc = (e - s).days
        return max(0, dc) / 365.0
    except Exception:
        return 0.0

def calculate_present_value(future_value: float, annual_rate: float, du: int) -> float:
    """
    Calcula o Valor Presente (VP) usando a capitalização composta padrão B3/DI.
    Fórmula: VP = VF / (1 + r)^(DU/252)
    """
    if du <= 0:
        return future_value
    return future_value / ((1 + annual_rate) ** (du / 252.0))

def deannualize_rate(rate_annual: float, du: int) -> float:
    """
    Converte taxa anual DI para o período (capitalização composta B3).
    """
    return (1 + rate_annual) ** (du / 252.0) - 1

if __name__ == "__main__":
    # Testes unitários rápidos
    hoje = date.today()
    vencimento = "2024-12-20" # Exemplo
    
    du = get_business_days(hoje, vencimento)
    t_anual = year_fraction_b3_du(hoje, vencimento)
    vp_exemplo = calculate_present_value(100.0, 0.1175, du) # 100 reais a 11.75% aa
    
    print(f"DEBUG SPREADHUNTER:")
    print(f"- Dias Úteis até {vencimento}: {du}")
    print(f"- T (DU/252): {t_anual:.4f}")
    print(f"- VP de R$100.00 (11.75% aa): R${vp_exemplo:.2f}")