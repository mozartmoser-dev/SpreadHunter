from dataclasses import dataclass
from datetime import date
from enum import Enum
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

from src.domain.services.calendario_b3 import dc_to_du, frac_du
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3


class TipoColarCalendario(Enum):
    ALTA = "Alta"
    BAIXA = "Baixa"
    NEUTRO = "Neutro"


@dataclass
class ResultadoColarCalendario:
    ativo: str
    vencimento_call: date
    vencimento_put: date
    dte_call: int
    dte_put: int
    dte_extra: int
    strike_call: float
    strike_put: float
    cod_call: str
    cod_put: str
    preco_ativo: float
    premio_call: float
    premio_put: float
    net_credito: float
    iv_call: float
    iv_put: float
    valor_put_venc_call: float
    pnl_stock: float
    pnl_projetado: float
    capital_empregado: float
    pct_retorno: float
    pct_cdi: float
    theta_call: float
    theta_put: float
    theta_liquido: float
    viavel: bool
    tipo: TipoColarCalendario
    r: float = 0.1450
    custo_b3: float = 0.0
    custo_ir: float = 0.0
    pct_cdi_liquido: float = 0.0
    be_baixa: float | None = None
    be_alta: float | None = None
    be_baixa_intrinseco: float | None = None
    be_alta_intrinseco: float | None = None


class CalculadoraColarCalendario:
    def __init__(self, taxa_cdi: float = 0.1450, premio_risco: float = 1.2, custos_b3: CalculadoraCustosB3 | None = None, taxa_ir: float | None = None):
        # CDI lido do banco (parametro taxa_cdi), usuario atualiza manualmente na tabela.
        # IR fixo em 15% porque 99,9% das operacoes sao swing trade.
        self.taxa_cdi = taxa_cdi
        self.premio_risco = premio_risco
        self.custos_b3 = custos_b3 or CalculadoraCustosB3(taxa_ir=taxa_ir)

    @staticmethod
    def black_scholes(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        if sigma <= 0 or T <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if option_type == 'call':
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    @staticmethod
    def bs_theta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        if sigma <= 0 or T <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        sqrt_T = np.sqrt(T)
        pdf_d1 = norm.pdf(d1)
        if option_type == 'call':
            theta = (-S * pdf_d1 * sigma) / (2 * sqrt_T) - r * K * np.exp(-r * T) * norm.cdf(d2)
        else:
            theta = (-S * pdf_d1 * sigma) / (2 * sqrt_T) + r * K * np.exp(-r * T) * norm.cdf(-d2)
        return theta / 365

    @staticmethod
    def implied_volatility(S: float, K: float, T: float, r: float, market_price: float, option_type: str) -> float | None:
        if market_price <= 0 or T <= 0:
            return None
        def f(sigma):
            return CalculadoraColarCalendario.black_scholes(S, K, T, r, sigma, option_type) - market_price
        try:
            return brentq(f, 1e-6, 5.0)
        except (ValueError, RuntimeError):
            return None

    def calcular_cdi_periodo(self, dias_uteis: int) -> float:
        if dias_uteis <= 0:
            return 0.0
        return (1 + self.taxa_cdi) ** (dias_uteis / 252) - 1

    @staticmethod
    def calcular_preco_ajustado_dividendos(
        dividendos: list[tuple[date, float]],
        preco_ativo: float,
        r: float,
        dte_max: int,
    ) -> float:
        hoje = date.today()
        total_pv = 0.0
        for data_ex, valor in dividendos:
            dias_ate_ex = (data_ex - hoje).days
            if dias_ate_ex <= 0 or dias_ate_ex > dte_max:
                continue
            t = dias_ate_ex / 365
            total_pv += valor * np.exp(-r * t)
        return preco_ativo - total_pv

    def classificar_tipo(self, preco_ativo: float, strike_call: float, strike_put: float) -> TipoColarCalendario:
        meio = (strike_call + strike_put) / 2
        dist = abs(preco_ativo - meio)
        limiar = (strike_call - strike_put) * 0.15
        if dist <= limiar:
            return TipoColarCalendario.NEUTRO
        if preco_ativo < meio:
            return TipoColarCalendario.ALTA
        return TipoColarCalendario.BAIXA

    @staticmethod
    def _pnl_at_call_expiry(
        S: float, S0: float, Kc: float, Kp: float,
        Pc: float, Pp: float, T_rem: float, rf: float, iv_p: float,
    ) -> float:
        stock_pnl = min(S, Kc) - S0
        call_pnl = Pc
        if T_rem > 0 and iv_p > 1e-10:
            d1 = (np.log(S / Kp) + (rf + 0.5 * iv_p ** 2) * T_rem) / (iv_p * np.sqrt(T_rem))
            d2 = d1 - iv_p * np.sqrt(T_rem)
            put_val = Kp * np.exp(-rf * T_rem) * norm.cdf(-d2) - S * norm.cdf(-d1)
        else:
            put_val = max(Kp - S, 0)
        return stock_pnl + call_pnl + (put_val - Pp)

    @staticmethod
    def _calcular_breakevens(
        S0: float, Kc: float, Kp: float,
        Pc: float, Pp: float, dte_extra: int, rf: float, iv_p: float,
    ) -> tuple[float | None, float | None]:
        from scipy.optimize import brentq
        T_rem = dte_extra / 365 if dte_extra > 0 else 0
        def _f(S):
            return CalculadoraColarCalendario._pnl_at_call_expiry(S, S0, Kc, Kp, Pc, Pp, T_rem, rf, iv_p)
        x_min = min(Kp, S0) * 0.85
        x_max = max(Kc, S0) * 1.15
        f_min = _f(x_min)
        f_kc = _f(Kc)
        f_max = _f(x_max)
        be_baixa = be_alta = None
        if f_min < 0 < f_kc:
            try:
                be_baixa = brentq(_f, x_min, Kc)
            except (ValueError, RuntimeError):
                pass
        if f_kc > 0 > f_max:
            try:
                be_alta = brentq(_f, Kc, x_max)
            except (ValueError, RuntimeError):
                pass
        return round(be_baixa, 2) if be_baixa else None, round(be_alta, 2) if be_alta else None

    @staticmethod
    def _calcular_breakevens_intrinseco(
        S0: float, Kc: float, Kp: float,
        Pc: float, Pp: float,
    ) -> tuple[float | None, float | None]:
        from scipy.optimize import brentq
        def _pnl_intrinseco(S):
            stock_pnl = min(S, Kc) - S0
            call_pnl = Pc
            put_val = max(Kp - S, 0)
            return stock_pnl + call_pnl + (put_val - Pp)
        x_min = min(Kp, S0) * 0.85
        x_max = max(Kc, S0) * 1.15
        f_min = _pnl_intrinseco(x_min)
        f_kc = _pnl_intrinseco(Kc)
        f_max = _pnl_intrinseco(x_max)
        be_baixa = be_alta = None
        if f_min < 0 < f_kc:
            try:
                be_baixa = brentq(_pnl_intrinseco, x_min, Kc)
            except (ValueError, RuntimeError):
                pass
        if f_kc > 0 > f_max:
            try:
                be_alta = brentq(_pnl_intrinseco, Kc, x_max)
            except (ValueError, RuntimeError):
                pass
        return round(be_baixa, 2) if be_baixa else None, round(be_alta, 2) if be_alta else None

    def calcular(
        self,
        preco_ativo: float,
        strike_call: float,
        strike_put: float,
        premio_call: float,
        premio_put: float,
        cod_call: str,
        cod_put: str,
        dte_call: int,
        dte_put: int,
        ativo: str,
        vencimento_call: date,
        vencimento_put: date,
        r: float | None = None,
        preco_compra_ativo: float | None = None,
        dividendos: list[tuple[date, float]] | None = None,
    ) -> ResultadoColarCalendario | None:
        if r is None:
            r = self.taxa_cdi

        if preco_ativo <= 0 or dte_call <= 0 or dte_put <= 0:
            return None
        if premio_call <= 0 or premio_put <= 0:
            return None

        T_call = dc_to_du(None, None, dte_call) / 252.0
        T_put = dc_to_du(None, None, dte_put) / 252.0
        dte_extra = dte_put - dte_call
        r_cont = np.log(1 + r)

        S_bs_call = preco_ativo
        S_bs_put = preco_ativo
        if dividendos:
            S_bs_call = self.calcular_preco_ajustado_dividendos(dividendos, preco_ativo, r, dte_call)
            S_bs_put = self.calcular_preco_ajustado_dividendos(dividendos, preco_ativo, r, dte_put)
            if S_bs_call <= 0 or S_bs_put <= 0:
                return None

        iv_call = self.implied_volatility(S_bs_call, strike_call, T_call, r_cont, premio_call, 'call')
        iv_put = self.implied_volatility(S_bs_put, strike_put, T_put, r_cont, premio_put, 'put')

        if iv_call is None or iv_put is None:
            return None

        preco_compra = preco_compra_ativo if (preco_compra_ativo and preco_compra_ativo > 0) else preco_ativo

        net_credito = premio_call - premio_put
        tipo = self.classificar_tipo(preco_ativo, strike_call, strike_put)

        theta_call = self.bs_theta(S_bs_call, strike_call, T_call, r_cont, iv_call, 'call')
        theta_put = self.bs_theta(S_bs_put, strike_put, T_put, r_cont, iv_put, 'put')
        theta_liquido = abs(theta_call) - abs(theta_put)

        T_put_rem = dc_to_du(None, None, dte_extra) / 252.0 if dte_extra > 0 else 0
        valor_put_vc = self.black_scholes(S_bs_call, strike_put, T_put_rem, r_cont, iv_put, 'put') if T_put_rem > 0 else 0

        # Modelo COBERTO: compra 100 acoes + short call + long put
        pnl_call = premio_call  # premio recebido, acao cobre exercicio
        pnl_stock = min(preco_ativo, strike_call) - preco_compra  # acao vendida a Kc se ITM
        pnl_put = valor_put_vc - premio_put
        pnl_projetado = pnl_call + pnl_stock + pnl_put

        if pnl_projetado <= 0:
            return None

        du_total = dc_to_du(None, None, dte_call)
        cdi_periodo = self.calcular_cdi_periodo(du_total)
        if cdi_periodo <= 0:
            return None

        capital_empregado = preco_compra + premio_put - premio_call

        strike_medio = (strike_call + strike_put) / 2
        custo_b3 = self.custos_b3.calcular_custos(strike_medio, n_pernas=2)
        pnl_projetado_liquido = max(pnl_projetado - custo_b3, 0.0)

        ganho_base = max(pnl_projetado_liquido, 0.0)
        custo_ir = self.custos_b3.ajustar_ir(ganho_base)
        pnl_projetado_ir = pnl_projetado_liquido - custo_ir

        pct_retorno = pnl_projetado_liquido / capital_empregado if capital_empregado > 0 else 0
        pct_cdi = pct_retorno / cdi_periodo if cdi_periodo > 0 else 0
        pct_cdi_liquido = (pnl_projetado_ir / capital_empregado) / cdi_periodo if capital_empregado > 0 and cdi_periodo > 0 else 0.0
        viavel = pct_cdi_liquido >= self.premio_risco

        be_baixa, be_alta = self._calcular_breakevens(
            preco_ativo, strike_call, strike_put,
            premio_call, premio_put, dte_extra, r, iv_put,
        )
        be_baixa_int, be_alta_int = self._calcular_breakevens_intrinseco(
            preco_ativo, strike_call, strike_put,
            premio_call, premio_put,
        )

        return ResultadoColarCalendario(
            ativo=ativo,
            vencimento_call=vencimento_call,
            vencimento_put=vencimento_put,
            dte_call=dte_call,
            dte_put=dte_put,
            dte_extra=dte_extra,
            strike_call=strike_call,
            strike_put=strike_put,
            cod_call=cod_call,
            cod_put=cod_put,
            preco_ativo=preco_ativo,
            premio_call=premio_call,
            premio_put=premio_put,
            net_credito=round(net_credito, 4),
            custo_b3=round(custo_b3, 4),
            custo_ir=round(custo_ir, 4),
            iv_call=round(iv_call * 100, 2),
            iv_put=round(iv_put * 100, 2),
            valor_put_venc_call=round(valor_put_vc, 4),
            pnl_stock=round(pnl_stock, 4),
            pnl_projetado=round(pnl_projetado, 4),
            capital_empregado=round(capital_empregado, 4),
            pct_retorno=round(pct_retorno * 100, 4),
            pct_cdi=round(pct_cdi, 4),
            pct_cdi_liquido=round(pct_cdi_liquido, 4),
            theta_call=round(theta_call * 100, 4),
            theta_put=round(theta_put * 100, 4),
            theta_liquido=round(theta_liquido * 100, 4),
            tipo=tipo,
            viavel=viavel,
            r=r,
            be_baixa=be_baixa,
            be_alta=be_alta,
            be_baixa_intrinseco=be_baixa_int,
            be_alta_intrinseco=be_alta_int,
        )

    @staticmethod
    def gerar_explicacao(r: 'ResultadoColarCalendario', taxa_cdi: float = 0.1450) -> str:
        import numpy as np
        from scipy.stats import norm

        S0 = r.preco_ativo
        Kc, Kp = r.strike_call, r.strike_put
        Pc, Pp = r.premio_call, r.premio_put
        T_rem = r.dte_extra / 365
        iv_p = r.iv_put / 100

        rf = getattr(r, 'r', 0.1450)

        def bs_put(S, K, T, sigma):
            if T <= 0 or sigma <= 0:
                return max(K - S, 0)
            d1 = (np.log(S / K) + (rf + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            return K * np.exp(-rf * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        cap = S0 + Pp - Pc
        net = Pc - Pp

        cenarios = []
        for S_T, label in [(S0 * 0.7, "Queda forte (S=−30%)"),
                           (S0 * 0.95, "Queda leve (S=−5%)"),
                           (S0, "Estável (S=0%)"),
                           (S0 * 1.05, "Alta leve (S=+5%)"),
                           (S0 * 1.4, "Alta forte (S=+40%)")]:
            if S_T > Kc:
                s_pnl = Kc - S0
                c_pnl = Pc
                put_bs = bs_put(S_T, Kp, T_rem, iv_p)
                p_pnl = put_bs - Pp
            else:
                put_bs = bs_put(S_T, Kp, T_rem, iv_p)
                pnl_no_ex = (S_T - S0) + Pc + (put_bs - Pp)
                pnl_ex = (Kp - S0) + Pc - Pp
                if pnl_ex > pnl_no_ex:
                    s_pnl, c_pnl, p_pnl = (Kp - S0), Pc, -Pp
                else:
                    s_pnl, c_pnl, p_pnl = (S_T - S0), Pc, (put_bs - Pp)
            total = s_pnl + c_pnl + p_pnl
            put_intrin = max(Kp - S_T, 0)
            put_extrin = put_bs - put_intrin
            cenarios.append((label, S_T, s_pnl, c_pnl, put_bs, put_intrin, put_extrin, p_pnl, total))

        call_Itm = S0 > Kc
        call_intrin = max(S0 - Kc, 0) if call_Itm else 0
        call_extrin = Pc - call_intrin
        if call_Itm:
            call_premio_txt = f"(intrínseco R$ {call_intrin:.2f} + extrínseco R$ {call_extrin:.2f})"
        else:
            call_premio_txt = "(prêmio inteiramente extrínseco)"

        lines = [
            "<h3>📖 Explicação — Collar Calendário Coberto</h3>",
            f"<p><b>{r.ativo}</b> &mdash; {r.tipo.value}</p>",
            "<hr>",
            "<p><b>O que é esta estratégia?</b><br>",
            "Você compra a ação, vende uma CALL de curto prazo e compra uma PUT de prazo maior. ",
            "O lucro vem da diferença de decaimento temporal: a CALL perde valor mais rápido que a PUT ",
            f"nos primeiros {r.dte_call} dias, enquanto a PUT ainda tem {r.dte_extra}d de vida útil.</p>",
            "<hr>",
            "<p><b>Montagem:</b></p>",
            "<ul>",
            f"<li>Comprar ação: <b>−R$ {S0:.2f}</b></li>",
            f"<li>Vender CALL {r.cod_call} K={Kc:.2f}: <b>+R$ {Pc:.2f}</b> {call_premio_txt}</li>",
            f"<li>Comprar PUT {r.cod_put} K={Kp:.2f}: <b>−R$ {Pp:.2f}</b></li>",
            f"<li><b>Capital empregado = R$ {cap:.2f}</b> ({S0:.2f} + {Pp:.2f} − {Pc:.2f})</li>",
            f"<li>Débito/Crédito líquido: <b>R$ {net:.2f}</b></li>",
            "</ul>",
            "<hr>",
            f"<p><b>Cenários no vencimento da CALL ({r.dte_call}d):</b></p>",
            "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; font-size:9pt;'>",
            "<tr style='background:#2d2d44;'>"
            "<th>Cenário</th><th>S_T</th><th>Ação</th><th>CALL</th>"
            "<th>PUT (BS)</th><th>Intrín</th><th>Extrín</th>"
            "<th>PnL Total</th></tr>",
        ]
        for cenario, S_T, s_pnl, c_pnl, put_bs, pint, pext, p_pnl, total in cenarios:
            cor = "#2ecc71" if total > 0 else "#e74c3c"
            lines.append(
                f"<tr>"
                f"<td>{cenario}</td><td>R$ {S_T:.2f}</td><td>R$ {s_pnl:.2f}</td>"
                f"<td>R$ {c_pnl:.2f}</td><td>R$ {put_bs:.2f}</td>"
                f"<td>R$ {pint:.2f}</td><td>R$ {pext:.2f}</td>"
                f"<td style='color:{cor};font-weight:bold;'>R$ {total:.2f}</td></tr>"
            )
        lines.append("</table>")
        lines.append("<hr>")

        c_baixa = cenarios[0]
        tot_baixa = c_baixa[8]
        sinal_b = "lucro" if tot_baixa >= 0 else "prejuízo"
        lines.append(
            f"<p><b>Se o ativo cai para R$ {c_baixa[1]:.2f}:</b><br>"
            f"A CALL expira OTM → fica com +R$ {c_baixa[3]:.2f}.<br>"
            f"A PUT vale R$ {c_baixa[4]:.2f} pelo modelo BS "
            f"(intrínseco=R$ {c_baixa[5]:.2f}, extrínseco=R$ {c_baixa[6]:.2f}).<br>"
            f"<b>Resultado: R$ {tot_baixa:.2f} ({sinal_b})</b> neste cenário.</p>"
        )

        c_proj = cenarios[2]
        call_itm_proj = S0 > Kc  # call esta ITM no spot atual?
        if call_itm_proj:
            call_texto = f"A CALL está ITM → ação vendida a R$ {Kc:.2f}, perda de R$ {c_proj[2]:.2f} na ação"
        else:
            call_texto = f"A CALL expira OTM → fica com +R$ {c_proj[3]:.2f}"
        lines.append(
            f"<p><b>Se o ativo mantém R$ {c_proj[1]:.2f} (cenário projetado):</b><br>"
            f"{call_texto}.<br>"
            f"A PUT ainda tem {r.dte_extra}d de vida, valendo R$ {c_proj[4]:.2f} "
            f"(intrínseco=R$ {c_proj[5]:.2f} + extrínseco=R$ {c_proj[6]:.2f}).<br>"
            f"<b>PnL = R$ {c_proj[8]:.2f}</b> ({r.pct_retorno:.2f}% / {r.pct_cdi:.2f}x CDI)</p>"
        )

        for idx, rotulo in [(4, "sobe para"), (3, "sobe levemente para")]:
            c_alta = cenarios[idx]
            tot_alta = c_alta[8]
            sinal_a = "lucro" if tot_alta >= 0 else "prejuízo"
            put_bs_a = c_alta[4]
            if put_bs_a < 0.01:
                put_texto = f"A PUT fica OTM → praticamente sem valor (BS=R$ {put_bs_a:.2f})"
            else:
                put_texto = f"A PUT fica OTM, mas ainda vale R$ {put_bs_a:.2f} (BS, {r.dte_extra}d restantes)"
            lines.append(
                f"<p><b>Se o ativo {rotulo} R$ {c_alta[1]:.2f}:</b><br>"
                f"A CALL está ITM → ação é vendida a R$ {Kc:.2f}, "
                f"{'lucro' if c_alta[2] >= 0 else 'perda'} de R$ {c_alta[2]:.2f} na ação.<br>"
                f"{put_texto}<br>"
                f"<b>Resultado: R$ {tot_alta:.2f} ({sinal_a}).</b></p>"
            )

        # Breakevens
        if r.be_baixa is not None or r.be_alta is not None:
            lines.append("<p><b>Breakevens B&S (com valor extrínseco da PUT):</b><br>")
            if r.be_baixa is not None:
                lines.append(f"BE Baixa: R$ {r.be_baixa:.2f}<br>")
            if r.be_alta is not None:
                lines.append(f"BE Alta: R$ {r.be_alta:.2f}<br>")
            if r.be_baixa is not None and r.be_alta is not None:
                lines.append("Considera o valor extrínseco residual da PUT no vencimento da CALL.</p>")
            else:
                lines.append("</p>")
        if r.be_baixa_intrinseco is not None or r.be_alta_intrinseco is not None:
            lines.append("<p><b>Breakevens Intrínseco (só valor intrínseco da PUT):</b><br>")
            if r.be_baixa_intrinseco is not None:
                lines.append(f"BE Baixa: R$ {r.be_baixa_intrinseco:.2f}<br>")
            if r.be_alta_intrinseco is not None:
                lines.append(f"BE Alta: R$ {r.be_alta_intrinseco:.2f}<br>")
            if r.be_baixa_intrinseco is not None and r.be_alta_intrinseco is not None:
                lines.append("Ignora valor extrínseco — cenário conservador (PUT vale só intrínseco).</p>")
            else:
                lines.append("</p>")
        if r.be_baixa is not None or r.be_alta is not None or r.be_baixa_intrinseco is not None or r.be_alta_intrinseco is not None:
            lines.append("<hr>")

        resumo_pnl = "lucro" if r.pnl_projetado >= 0 else "prejuízo"
        ext = abs(r.pnl_projetado)
        if call_Itm:
            lines.append(
                f"<p><b>Resumo:</b><br>"
                f"A CALL está ITM (acima do strike). O prêmio de R$ {Pc:.2f} "
                f"cobre a perda de R$ {S0 - Kc:.2f} na venda da ação. "
                f"O {resumo_pnl} projetado de R$ {ext:.2f} "
                f"({r.pct_retorno:.2f}% / {r.pct_cdi:.2f}x CDI) é o "
                f"extrínseco da CALL menos o custo líquido da PUT.</p>"
            )
        else:
            lines.append(
                f"<p><b>Resumo:</b><br>"
                f"Esta estratégia aposta que o ativo estará <b>próximo de R$ {Kc:.2f}</b> "
                f"no vencimento da CALL. O {resumo_pnl} projetado de R$ {ext:.2f} "
                f"({r.pct_retorno:.2f}% / {r.pct_cdi:.2f}x CDI) vem do "
                f"valor extrínseco residual da PUT. O resultado real "
                f"depende de onde o ativo estará naquele dia.</p>"
            )

        return "\n".join(lines)
