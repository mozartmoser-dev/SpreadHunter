from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AnaliseMercadoResult:
    curva_status: str      # "STRESS" / "ALÍVIO"
    curva_seta: str        # "↑" / "↓"
    curva_cor: str         # "#e74c3c" / "#2ecc71"
    vetor: str             # "RISK-ON" / "RISK-OFF" / "COMMODITIES" / "DEFENSIVO" / "MISTO"
    vetor_cor: str         # cor hex para exibição


class MarketAnalyzer:

    @staticmethod
    def analisar_curva_di(di1f33_var_pontos: float) -> tuple[str, str, str]:
        if di1f33_var_pontos > 0:
            return "STRESS", "↑", "#e74c3c"
        return "ALÍVIO", "↓", "#2ecc71"

    @staticmethod
    def analisar_vetor(win_var: float, wdo_var: float, di1f33_var_pontos: float,
                       brent_var: float = 0.0, sgx_var: float = 0.0) -> str:
        if win_var > 0 and wdo_var < 0 and di1f33_var_pontos < 0:
            return "RISK-ON"
        if win_var < 0 and wdo_var > 0 and di1f33_var_pontos > 0:
            return "RISK-OFF"
        if win_var > 0 and di1f33_var_pontos > 0 and brent_var > 0 and sgx_var > 0:
            return "COMMODITIES"
        if wdo_var > 0 and di1f33_var_pontos > 0:
            return "DEFENSIVO"
        return "MISTO"

    @staticmethod
    def vetor_cor(vetor: str) -> str:
        return {
            "RISK-ON": "#2ecc71",
            "RISK-OFF": "#e74c3c",
            "COMMODITIES": "#f0c040",
            "DEFENSIVO": "#e67e22",
            "MISTO": "#9090b0",
        }.get(vetor, "#9090b0")

    @staticmethod
    def cor_heatmap(var: float) -> str:
        if var <= -1.5:
            return "#e74c3c"
        if var < 0:
            return "#c0392b"
        if var == 0:
            return "#606080"
        if var < 1.5:
            return "#27ae60"
        return "#2ecc71"

    @staticmethod
    def icone_heatmap(var: float) -> str:
        if var <= -1.5:
            return "▼"
        if var < 0:
            return "▽"
        if var == 0:
            return "—"
        if var < 1.5:
            return "△"
        return "▲"

    @staticmethod
    def deve_emitir(cod: str) -> bool:
        cod_u = cod.upper()
        if cod_u == "DI1F27":
            return True
        if cod_u == "DI1F33":
            return True
        return True

    @classmethod
    def processar_tick(cls, codigo: str, preco: float,
                       ref_prices: dict[str, float],
                       ref_settled: set[str]) -> dict:
        if not cls.deve_emitir(codigo):
            return {"var": 0.0, "var_str": "", "cor": "#888"}
        if codigo not in ref_settled and preco > 0:
            if codigo not in ref_prices:
                ref_prices[codigo] = preco
            ref_settled.add(codigo)
        ref = ref_prices.get(codigo) or preco
        var = ((preco - ref) / ref * 100) if ref > 0 else 0.0
        cor = cls.cor_heatmap(var)
        if preco > 0:
            var_str = f"{var:+.2f}%"
            if abs(var) >= 1.5:
                var_str = f"{cls.icone_heatmap(var)} {var_str}"
        else:
            var_str = ""
        return {"var": var, "var_str": var_str, "cor": cor}
