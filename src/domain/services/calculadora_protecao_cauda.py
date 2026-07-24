from dataclasses import dataclass
import json
import logging
import math
from typing import TYPE_CHECKING

from src.domain.services.calculadora_cauda_assincrona import ResultadoCaudaAssincrona

if TYPE_CHECKING:
    from src.domain.services.pipeline_tracker import PipelineTracker

logger = logging.getLogger(__name__)


_LOTE = 100

try:
    from scipy.stats import norm as _norm
    def _phi(x: float) -> float:
        return float(_norm.cdf(x))
except ImportError:
    def _phi(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(slots=True)
class ResultadoProtecaoCauda:
    id_chassi: str | None
    ativo: str
    lado_protegido: str  # 'call' | 'put' | 'ambos' | 'nenhum'
    naked_call_frac: float
    naked_put_gap: float
    strike_protecao_call: float | None
    strike_protecao_put: float | None
    premio_ask_call: float | None
    premio_ask_put: float | None
    qtd_protecao_call: int
    qtd_protecao_put: int
    custo_protecao_call: float
    custo_protecao_put: float
    custo_protecao_total: float
    pnl_sem_protecao: float
    pnl_liquido_pos_protecao: float
    viavel_call: bool
    viavel_put: bool
    viavel: bool
    bwb_modo: str = "simples"
    strikes_bwb_call: str | None = None
    strikes_bwb_put: str | None = None
    premios_bwb_call: str | None = None
    premios_bwb_put: str | None = None
    custo_borboleta_call: float = 0.0
    custo_borboleta_put: float = 0.0
    lotes_bwb_call: int = 0
    lotes_bwb_put: int = 0
    razao_convexidade_call: float = 1.0
    razao_convexidade_put: float = 1.0
    score_ev: float = 0.0
    score_ev_pct: float = 0.0
    prob_zona_a: float = 0.0
    prob_zona_b: float = 0.0
    prob_zona_c: float = 0.0
    prob_zona_d: float = 0.0
    ev_zona_a: float = 0.0
    ev_zona_b: float = 0.0
    ev_zona_c: float = 0.0
    ev_zona_d: float = 0.0
    zonas_ev_json: str | None = None


class CalculadoraProtecaoCauda:
    """Camada de proteção via asa quebrada (BWB) sobre Collar Calendário otimizado por ratio.

    DEPOIS que uma variante de ResultadoCaudaAssincrona já foi escolhida,
    avalia se/como proteger a exposição naked.

    Dois modos:
      - 'simples': compra 1 opção OTM por lado (comportamento atual, legado)
      - 'borboleta': monta Broken Wing Butterfly com 3 strikes por lado
        (W1 compra + Corpo vende 2x + W2 compra), autofinanciada pelo corpo.
    """

    NAKED_FRAC_MINIMO = 0.02

    @staticmethod
    def _bs_call_ev(S0: float, K: float, T: float, r_cont: float, sigma_T: float) -> float:
        if sigma_T <= 0 or T <= 0:
            return max(0.0, S0 - K)
        d1 = (math.log(max(S0, 1e-9) / max(K, 1e-9)) + r_cont * T) / sigma_T + sigma_T / 2.0
        d2 = d1 - sigma_T
        return S0 * _phi(d1) - K * math.exp(-r_cont * T) * _phi(d2)

    @staticmethod
    def _d2(S0: float, K: float, T: float, r_cont: float, sigma_T: float) -> float:
        if sigma_T <= 0 or T <= 0:
            return 10.0 if S0 > K else -10.0
        return (math.log(max(S0, 1e-9) / max(K, 1e-9)) + (r_cont - sigma_T * sigma_T / 2.0) * T) / sigma_T

    @staticmethod
    def _calcular_score_probabilistico(
        resultado: "ResultadoCaudaAssincrona",
        protecao: "ResultadoProtecaoCauda",
        qtd_acao: int,
        taxa_cdi: float,
    ) -> dict:
        S0 = resultado.preco_ativo
        Kc = resultado.strike_call
        Kp = resultado.strike_put
        n_ratio = resultado.ratio_call
        m_ratio = resultado.ratio_put
        sigma_T = resultado.sigma_periodo
        T = resultado.dte_call / 365.0

        if sigma_T <= 0 or T <= 0:
            return {"score_ev": 0.0, "score_ev_pct": 0.0,
                    "p_a": 0, "p_b": 0, "p_c": 0, "p_d": 0,
                    "ev_a": 0.0, "ev_b": 0.0, "ev_c": 0.0, "ev_d": 0.0}

        r_cont = math.log(1.0 + taxa_cdi)

        Kprot = protecao.strike_protecao_call or Kc * 1.5
        raz = max(protecao.razao_convexidade_call, 1.0)
        qtd_prot = max(protecao.qtd_protecao_call, 0)
        custo_prot = protecao.custo_protecao_call + protecao.custo_protecao_put

        credito_por_acao = n_ratio * resultado.premio_call - m_ratio * resultado.premio_put
        credito_total = qtd_acao * credito_por_acao

        F = S0 * math.exp(r_cont * T)
        disc = math.exp(-r_cont * T)

        d2c = CalculadoraProtecaoCauda._d2(S0, Kc, T, r_cont, sigma_T)
        d2p = CalculadoraProtecaoCauda._d2(S0, Kp, T, r_cont, sigma_T)
        d2prot = CalculadoraProtecaoCauda._d2(S0, Kprot, T, r_cont, sigma_T)
        d1c = d2c + sigma_T
        d1p = d2p + sigma_T
        d1prot = d2prot + sigma_T

        BS_call_c = CalculadoraProtecaoCauda._bs_call_ev(S0, Kc, T, r_cont, sigma_T)
        BS_put_p = Kp * disc * _phi(-d2p) - S0 * _phi(-d1p)
        BS_call_prot = CalculadoraProtecaoCauda._bs_call_ev(S0, Kprot, T, r_cont, sigma_T)

        ev_pnl = (credito_total
                  + qtd_acao * S0 * (1.0 - disc)
                  - n_ratio * qtd_acao * BS_call_c
                  + m_ratio * qtd_acao * BS_put_p
                  + raz * qtd_prot * BS_call_prot
                  - custo_prot)

        ev_pct = (ev_pnl / max(resultado.capital_base, 1.0)) * 100.0 if resultado.capital_base > 0 else 0.0

        # Probabilidades por zona (mutuamente exclusivas)
        if Kp <= Kc:
            p_a = _phi(-d2p)
            p_b = max(0.0, _phi(d2p) - _phi(d2c))
            p_c = max(0.0, _phi(d2c) - _phi(d2prot))
            p_d = _phi(d2prot)
        else:
            p_a = _phi(-d2c)
            p_b = 0.0
            p_c = max(0.0, _phi(d2c) - _phi(d2prot))
            p_d = _phi(d2prot)

        # Spot esperado condicional por zona (truncated log-normal)
        def _e_spot_cond(d1_a, d2_a, d1_b, d2_b):
            num = F * (_phi(d1_a) - _phi(d1_b))
            den = max(_phi(d2_a) - _phi(d2_b), 1e-12)
            return num / den

        if Kp <= Kc:
            e_s_a = F * _phi(-d1p) / max(_phi(-d2p), 1e-12)
        else:
            e_s_a = F * _phi(-d1c) / max(_phi(-d2c), 1e-12)
        e_s_b = _e_spot_cond(d1p, d2p, d1c, d2c) if p_b > 0 else S0
        e_s_c = _e_spot_cond(d1c, d2c, d1prot, d2prot) if p_c > 0 else S0
        e_s_d = F * _phi(d1prot) / max(_phi(d2prot), 1e-12)

        # PnL linear em cada zona
        cpa = credito_por_acao

        def _pnl_zona(S_med: float) -> float:
            stock = qtd_acao * (S_med - S0)
            call_pay = n_ratio * qtd_acao * max(0.0, S_med - Kc)
            put_pay = m_ratio * qtd_acao * max(0.0, Kp - S_med)
            prot_pay = raz * qtd_prot * max(0.0, S_med - Kprot)
            return credito_total + stock - call_pay + put_pay + prot_pay - custo_prot

        ev_a = _pnl_zona(e_s_a) * p_a
        ev_b = _pnl_zona(e_s_b) * p_b
        ev_c = _pnl_zona(e_s_c) * p_c
        ev_d = _pnl_zona(e_s_d) * p_d

        return {
            "score_ev": round(ev_pnl, 2),
            "score_ev_pct": round(ev_pct, 4),
            "p_a": round(p_a, 4), "p_b": round(p_b, 4),
            "p_c": round(p_c, 4), "p_d": round(p_d, 4),
            "ev_a": round(ev_a, 2), "ev_b": round(ev_b, 2),
            "ev_c": round(ev_c, 2), "ev_d": round(ev_d, 2),
        }

    @staticmethod
    def avaliar(
        resultado: ResultadoCaudaAssincrona,
        strikes_call_candidatos: list[dict] | None = None,
        strikes_put_candidatos: list[dict] | None = None,
        qtd_acao: int = 100,
        n_sigma: float = 2.0,
        limite_protecao_pct: float = 0.35,
        limite_protecao_pct_rendimento: float = 0.20,
        limite_protecao_pct_plato: float = 0.45,
        limite_protecao_pct_protecao: float = 0.70,
        calda_preco_min_opcao: float = 0.01,
        cab_minimo: int = 1,
        fator_seguranca_liquidez: float = 0.2,
        razao_convexidade_max: float = 1.5,
        spread_maximo_pct: float = 0.20,
        taxa_cdi: float = 0.1425,
        pipeline_tracker: "PipelineTracker | None" = None,
        bwb_modo: str = "simples",
    ) -> ResultadoProtecaoCauda | None:
        naked_call_frac = max(0.0, resultado.ratio_call - 1.0)
        naked_put_gap = max(0.0, 1.0 - resultado.ratio_put)

        if (
            naked_call_frac < CalculadoraProtecaoCauda.NAKED_FRAC_MINIMO
            and naked_put_gap < CalculadoraProtecaoCauda.NAKED_FRAC_MINIMO
        ):
            return None

        ganho_extra_ratio = resultado.pnl_com_ratio - resultado.pnl_base

        mapa_limite = {
            "Rendimento": limite_protecao_pct_rendimento,
            "Platô": limite_protecao_pct_plato,
            "Proteção": limite_protecao_pct_protecao,
        }
        limite_efetivo = mapa_limite.get(resultado.estagio, limite_protecao_pct)

        usar_borboleta = bwb_modo == "borboleta"

        if usar_borboleta:
            be_alvo_call = resultado.breakeven_direito
            be_alvo_put = resultado.breakeven_esquerdo
            s_target_call = be_alvo_call if be_alvo_call and be_alvo_call > resultado.preco_ativo else (
                resultado.preco_ativo * (1.0 + n_sigma * resultado.sigma_periodo)
            )
            s_target_put = be_alvo_put if be_alvo_put and be_alvo_put < resultado.preco_ativo else (
                resultado.preco_ativo * (1.0 - n_sigma * resultado.sigma_periodo)
            )
        else:
            s_target_call = resultado.preco_ativo * (1.0 + n_sigma * resultado.sigma_periodo)
            s_target_put = resultado.preco_ativo * (1.0 - n_sigma * resultado.sigma_periodo)

        s_eficiencia_call = resultado.preco_ativo * (1.0 + n_sigma * 1.5 * resultado.sigma_periodo)
        s_eficiencia_put = resultado.preco_ativo * (1.0 - n_sigma * 1.5 * resultado.sigma_periodo)

        if usar_borboleta:
            info_call = CalculadoraProtecaoCauda._avaliar_borboleta(
                lado="call",
                naked_frac=naked_call_frac,
                strikes_candidatos=strikes_call_candidatos or [],
                s_alvo=s_target_call,
                acima_do_target=True,
                qtd_acao=qtd_acao,
                ganho_extra_ratio=ganho_extra_ratio,
                limite_protecao_pct=limite_efetivo,
                calda_preco_min_opcao=calda_preco_min_opcao,
                cab_minimo=cab_minimo,
                fator_seguranca_liquidez=fator_seguranca_liquidez,
                pipeline_tracker=pipeline_tracker,
            )
            info_put = CalculadoraProtecaoCauda._avaliar_borboleta(
                lado="put",
                naked_frac=naked_put_gap,
                strikes_candidatos=strikes_put_candidatos or [],
                s_alvo=s_target_put,
                acima_do_target=False,
                qtd_acao=qtd_acao,
                ganho_extra_ratio=ganho_extra_ratio,
                limite_protecao_pct=limite_efetivo,
                calda_preco_min_opcao=calda_preco_min_opcao,
                cab_minimo=cab_minimo,
                fator_seguranca_liquidez=fator_seguranca_liquidez,
                pipeline_tracker=pipeline_tracker,
            )
        else:
            info_call = CalculadoraProtecaoCauda._avaliar_lado(
                lado="call",
                naked_frac=naked_call_frac,
                strikes_candidatos=strikes_call_candidatos or [],
                s_target=s_target_call,
                acima_do_target=True,
                qtd_acao=qtd_acao,
                ganho_extra_ratio=ganho_extra_ratio,
                limite_protecao_pct=limite_efetivo,
                calda_preco_min_opcao=calda_preco_min_opcao,
                cab_minimo=cab_minimo,
                fator_seguranca_liquidez=fator_seguranca_liquidez,
                razao_convexidade_max=razao_convexidade_max,
                spread_maximo_pct=spread_maximo_pct,
                s_eficiencia=s_eficiencia_call,
                estagio=resultado.estagio,
                pipeline_tracker=pipeline_tracker,
            )
            info_put = CalculadoraProtecaoCauda._avaliar_lado(
                lado="put",
                naked_frac=naked_put_gap,
                strikes_candidatos=strikes_put_candidatos or [],
                s_target=s_target_put,
                acima_do_target=False,
                qtd_acao=qtd_acao,
                ganho_extra_ratio=ganho_extra_ratio,
                limite_protecao_pct=limite_efetivo,
                calda_preco_min_opcao=calda_preco_min_opcao,
                cab_minimo=cab_minimo,
                fator_seguranca_liquidez=fator_seguranca_liquidez,
                razao_convexidade_max=razao_convexidade_max,
                spread_maximo_pct=spread_maximo_pct,
                s_eficiencia=s_eficiencia_put,
                estagio=resultado.estagio,
                pipeline_tracker=pipeline_tracker,
            )

        custo_total = info_call["custo"] + info_put["custo"]
        pnl_liquido = resultado.pnl_com_ratio - custo_total

        lados = []
        if info_call["viavel"]:
            lados.append("call")
        if info_put["viavel"]:
            lados.append("put")
        if not lados:
            lados.append("nenhum")

        lado_protegido = "ambos" if len(lados) == 2 else lados[0]

        provisorio = ResultadoProtecaoCauda(
            id_chassi=resultado.id_chassi,
            ativo=resultado.ativo,
            lado_protegido=lado_protegido,
            naked_call_frac=naked_call_frac,
            naked_put_gap=naked_put_gap,
            strike_protecao_call=info_call.get("strike"),
            strike_protecao_put=info_put.get("strike"),
            premio_ask_call=info_call.get("premio_ask"),
            premio_ask_put=info_put.get("premio_ask"),
            qtd_protecao_call=info_call.get("qtd", 0),
            qtd_protecao_put=info_put.get("qtd", 0),
            custo_protecao_call=info_call.get("custo", 0.0),
            custo_protecao_put=info_put.get("custo", 0.0),
            custo_protecao_total=round(custo_total, 2),
            pnl_sem_protecao=resultado.pnl_com_ratio,
            pnl_liquido_pos_protecao=round(pnl_liquido, 2),
            viavel_call=info_call.get("viavel", False),
            viavel_put=info_put.get("viavel", False),
            viavel=info_call.get("viavel", False) or info_put.get("viavel", False),
            bwb_modo=bwb_modo,
            strikes_bwb_call=info_call.get("strikes_bwb"),
            strikes_bwb_put=info_put.get("strikes_bwb"),
            premios_bwb_call=info_call.get("premios_bwb"),
            premios_bwb_put=info_put.get("premios_bwb"),
            custo_borboleta_call=round(info_call.get("custo_borboleta", 0.0), 2),
            custo_borboleta_put=round(info_put.get("custo_borboleta", 0.0), 2),
            lotes_bwb_call=info_call.get("lotes_bwb", 0),
            lotes_bwb_put=info_put.get("lotes_bwb", 0),
            razao_convexidade_call=info_call.get("razao_convexidade", 1.0),
            razao_convexidade_put=info_put.get("razao_convexidade", 1.0),
        )

        ev = CalculadoraProtecaoCauda._calcular_score_probabilistico(
            resultado=resultado,
            protecao=provisorio,
            qtd_acao=qtd_acao,
            taxa_cdi=taxa_cdi,
        )
        provisorio.score_ev = ev["score_ev"]
        provisorio.score_ev_pct = ev["score_ev_pct"]
        provisorio.prob_zona_a = ev.get("p_a", 0.0)
        provisorio.prob_zona_b = ev.get("p_b", 0.0)
        provisorio.prob_zona_c = ev.get("p_c", 0.0)
        provisorio.prob_zona_d = ev.get("p_d", 0.0)
        provisorio.ev_zona_a = ev.get("ev_a", 0.0)
        provisorio.ev_zona_b = ev.get("ev_b", 0.0)
        provisorio.ev_zona_c = ev.get("ev_c", 0.0)
        provisorio.ev_zona_d = ev.get("ev_d", 0.0)
        try:
            provisorio.zonas_ev_json = json.dumps({
                "p": [ev.get("p_a", 0), ev.get("p_b", 0), ev.get("p_c", 0), ev.get("p_d", 0)],
                "ev": [ev.get("ev_a", 0), ev.get("ev_b", 0), ev.get("ev_c", 0), ev.get("ev_d", 0)],
            })
        except Exception:
            provisorio.zonas_ev_json = None

        return provisorio

    @staticmethod
    def _avaliar_lado(
        lado: str,
        naked_frac: float,
        strikes_candidatos: list[dict],
        s_target: float,
        acima_do_target: bool,
        qtd_acao: int,
        ganho_extra_ratio: float,
        limite_protecao_pct: float,
        calda_preco_min_opcao: float,
        cab_minimo: int,
        fator_seguranca_liquidez: float = 0.2,
        razao_convexidade_max: float = 1.5,
        spread_maximo_pct: float = 0.20,
        s_eficiencia: float | None = None,
        estagio: str = "",
        pipeline_tracker: "PipelineTracker | None" = None,
    ) -> dict:
        def _stage(nome: str, entrada: int, saida: int, msg: str = "") -> None:
            if pipeline_tracker is not None:
                pipeline_tracker.add_stage(nome, entrada, saida, msg)

        n_entrada = len(strikes_candidatos) if strikes_candidatos else 0
        _stage(f"BWB {lado} — entrada", n_entrada, n_entrada)
        if naked_frac < CalculadoraProtecaoCauda.NAKED_FRAC_MINIMO or not strikes_candidatos:
            if n_entrada == 0:
                logger.debug("BWB _avaliar_lado [%s]: 0 strikes na entrada — sem candidatos", lado)
                _stage(f"BWB {lado} — entrada", n_entrada, 0, "sem candidatos")
            return {
                "strike": None, "premio_ask": None, "qtd": 0, "custo": 0.0, "viavel": False,
                "razao_convexidade": 1.0,
            }

        if s_eficiencia is None:
            s_eficiencia = s_target

        qtd_bruta = naked_frac * qtd_acao
        qtd_lote = max(1, int(qtd_bruta / _LOTE + 0.5)) * _LOTE

        limite_liquidez = max(cab_minimo, qtd_lote * fator_seguranca_liquidez)

        filtrados = []
        for s in strikes_candidatos:
            vol_ask = s.get("vol_ask", 0) or 0
            vol_bid = s.get("vol_bid", 0) or 0
            premio_ask = s.get("premio_ask", 0) or 0
            strike = s.get("strike") or 0
            if (
                min(vol_ask, vol_bid) < limite_liquidez
                or premio_ask < calda_preco_min_opcao
                or strike <= 0
            ):
                continue
            bid = s.get("premio_bid", 0) or 0
            if bid > 0 and premio_ask > 0:
                spread_pct = (premio_ask - bid) / premio_ask
                if spread_pct > spread_maximo_pct:
                    continue
            filtrados.append(s)

        n_pos_liquidez = len(filtrados)
        _stage(f"BWB {lado} — liquidez", n_entrada, n_pos_liquidez,
               f"limite={limite_liquidez:.0f} preco_min={calda_preco_min_opcao:.4f} spread_max={spread_maximo_pct:.0%}")

        if n_pos_liquidez == 0:
            logger.debug(
                "BWB _avaliar_lado [%s]: %d candidatos na entrada, 0 passaram liquidez "
                "(limite=%.0f, preco_min=%.4f)",
                lado, n_entrada, limite_liquidez, calda_preco_min_opcao,
            )
            return {
                "strike": None, "premio_ask": None, "qtd": 0, "custo": 0.0, "viavel": False,
                "razao_convexidade": 1.0,
            }

        if acima_do_target:
            filtrados = [s for s in filtrados if s["strike"] >= s_target]
        else:
            filtrados = [s for s in filtrados if s["strike"] <= s_target]
        n_pos_direcao = len(filtrados)
        _stage(f"BWB {lado} — direção", n_pos_liquidez, n_pos_direcao,
               f"target={s_target:.2f}")

        if n_pos_direcao == 0:
            logger.debug(
                "BWB _avaliar_lado [%s]: %d passaram liquidez, 0 passaram direcao "
                "(target=%.2f, %s)",
                lado, n_pos_liquidez, s_target,
                "strike >= target" if acima_do_target else "strike <= target",
            )
            return {
                "strike": None, "premio_ask": None, "qtd": 0, "custo": 0.0, "viavel": False,
                "razao_convexidade": 1.0,
            }

        def _eficiencia(s):
            strike = s["strike"]
            premio = s.get("premio_ask", 0) or 0
            custo = premio * qtd_lote
            if custo <= 0:
                return -1.0
            if acima_do_target:
                perda_evitada = max(0.0, s_eficiencia - strike) * qtd_lote
            else:
                perda_evitada = max(0.0, strike - s_eficiencia) * qtd_lote
            return perda_evitada / custo

        escolha = max(filtrados, key=_eficiencia)

        premio_ask = escolha.get("premio_ask", 0) or 0
        razao_usada = 1.0
        if estagio == "Proteção" and razao_convexidade_max > 1.0:
            max_steps = int((razao_convexidade_max - 1.0) / 0.1)
            for step in range(max_steps, -1, -1):
                razao_teste = round(1.0 + step * 0.1, 1)
                qtd_teste = max(1, int((naked_frac * razao_teste) * qtd_acao / _LOTE + 0.5)) * _LOTE
                custo_teste = premio_ask * qtd_teste
                if custo_teste <= ganho_extra_ratio * limite_protecao_pct:
                    razao_usada = razao_teste
                    qtd_lote = qtd_teste
                    break
            else:
                if estagio == "Proteção":
                    logger.debug(
                        "BWB _avaliar_lado [%s]: Proteção com razão=1.0 custo=%.2f > limite=%.2f",
                        lado, premio_ask * qtd_lote, ganho_extra_ratio * limite_protecao_pct,
                    )

        custo = premio_ask * qtd_lote

        viavel = ganho_extra_ratio > 0 and custo <= ganho_extra_ratio * limite_protecao_pct
        _stage(f"BWB {lado} — custo", n_pos_direcao, 1 if viavel else 0,
               f"custo={custo:.2f} limite={ganho_extra_ratio * limite_protecao_pct:.2f}" if not viavel
               else f"K={escolha['strike']:.2f} custo={custo:.2f} razao={razao_usada}")

        if not viavel:
            logger.debug(
                "BWB _avaliar_lado [%s]: strike K=%.2f escolhido, custo=%.2f > limite=%.2f "
                "(ganho_extra=%.2f * %.0f%%), reprovado",
                lado, escolha["strike"], custo,
                ganho_extra_ratio * limite_protecao_pct,
                ganho_extra_ratio, limite_protecao_pct * 100,
            )

        return {
            "strike": escolha["strike"] if viavel else None,
            "premio_ask": premio_ask if viavel else None,
            "qtd": qtd_lote if viavel else 0,
            "custo": round(custo, 2) if viavel else 0.0,
            "viavel": viavel,
            "razao_convexidade": razao_usada,
        }

    @staticmethod
    def _avaliar_borboleta(
        lado: str,
        naked_frac: float,
        strikes_candidatos: list[dict],
        s_alvo: float,
        acima_do_target: bool,
        qtd_acao: int,
        ganho_extra_ratio: float,
        limite_protecao_pct: float,
        calda_preco_min_opcao: float,
        cab_minimo: int,
        fator_seguranca_liquidez: float = 0.2,
        pipeline_tracker: "PipelineTracker | None" = None,
    ) -> dict:
        """Monta Broken Wing Butterfly com 3 strikes reais do RTD.

        Estrutura: COMPRA 1x W1, VENDE 2x Corpo, COMPRA 1x W2.
        W1 é a asa mais próxima do dinheiro, W2 a asa quebrada (mais OTM).
        O corpo financia as asas: se premio_Corpo * 2 > premio_W1 + premio_W2,
        a borboleta é creditícia (custo negativo).

        Retorna dict com campos da borboleta + fallback 'simples' se inviável.
        """

        def _stage(nome: str, entrada: int, saida: int, msg: str = "") -> None:
            if pipeline_tracker is not None:
                pipeline_tracker.add_stage(nome, entrada, saida, msg)

        n_entrada = len(strikes_candidatos) if strikes_candidatos else 0
        _stage(f"BWB_B {lado} — entrada", n_entrada, n_entrada)

        if naked_frac < CalculadoraProtecaoCauda.NAKED_FRAC_MINIMO or n_entrada < 3:
            _stage(f"BWB_B {lado} — entrada", n_entrada, 0,
                   "frac < min" if naked_frac < CalculadoraProtecaoCauda.NAKED_FRAC_MINIMO else "< 3 strikes")
            return {
                "strike": None, "premio_ask": None, "qtd": 0, "custo": 0.0,
                "viavel": False, "strikes_bwb": None, "premios_bwb": None,
                "custo_borboleta": 0.0, "lotes_bwb": 0,
            }

        qtd_bruta = naked_frac * qtd_acao
        qtd_lote = max(1, round(qtd_bruta / _LOTE)) * _LOTE
        lotes_bwb = max(1, round(qtd_lote / _LOTE))

        limite_liquidez = max(cab_minimo, qtd_lote * fator_seguranca_liquidez)

        filtrados = []
        for s in strikes_candidatos:
            vol_ask = s.get("vol_ask", 0) or 0
            vol_bid = s.get("vol_bid", 0) or 0
            cab = min(vol_ask, vol_bid)
            premio = s.get("premio_ask", 0) or 0
            strike = s.get("strike", 0) or 0
            if cab >= limite_liquidez and premio >= calda_preco_min_opcao and strike > 0:
                if acima_do_target and strike >= s_alvo:
                    filtrados.append(s)
                elif not acima_do_target and strike <= s_alvo:
                    filtrados.append(s)

        n_pos_direcao = len(filtrados)
        _stage(f"BWB_B {lado} — dir+liq", n_entrada, n_pos_direcao,
               f"limite={limite_liquidez:.0f} target={s_alvo:.2f}")

        if n_pos_direcao < 3:
            logger.debug(
                "BWB borboleta [%s]: apenas %d strikes na direcao, precisa >= 3",
                lado, n_pos_direcao,
            )
            return {
                "strike": None, "premio_ask": None, "qtd": 0, "custo": 0.0,
                "viavel": False, "strikes_bwb": None, "premios_bwb": None,
                "custo_borboleta": 0.0, "lotes_bwb": 0,
            }

        if acima_do_target:
            filtrados.sort(key=lambda s: s["strike"])
        else:
            filtrados.sort(key=lambda s: s["strike"], reverse=True)

        orcamento = ganho_extra_ratio * limite_protecao_pct
        melhor = None

        for i in range(len(filtrados) - 2):
            w1 = filtrados[i]
            p1 = w1.get("premio_ask", 0) or 0
            for j in range(i + 1, len(filtrados) - 1):
                corpo = filtrados[j]
                pc = corpo.get("premio_ask", 0) or 0
                for k in range(j + 1, len(filtrados)):
                    w2 = filtrados[k]
                    p2 = w2.get("premio_ask", 0) or 0
                    custo_por_lote = p1 + p2 - 2.0 * pc
                    custo_total = custo_por_lote * lotes_bwb * 100

                    if custo_total > orcamento:
                        continue

                    distancia = abs(corpo["strike"] - w1["strike"])
                    if melhor is None or custo_total < melhor[0]:
                        melhor = (custo_total, custo_por_lote, w1, corpo, w2, lotes_bwb)

        if melhor is None:
            logger.debug(
                "BWB borboleta [%s]: %d strikes, nenhuma tripla dentro do orcamento R$%.2f",
                lado, n_pos_direcao, orcamento,
            )
            _stage(f"BWB_B {lado} — custo", n_pos_direcao, 0,
                   f"orcamento={orcamento:.2f} — nenhuma tripla")
            return {
                "strike": None, "premio_ask": None, "qtd": 0, "custo": 0.0,
                "viavel": False, "strikes_bwb": None, "premios_bwb": None,
                "custo_borboleta": 0.0, "lotes_bwb": 0,
            }

        custo_total, custo_por_lote, w1, corpo, w2, lotes = melhor
        viavel = orcamento > 0 and custo_total <= orcamento

        strikes_str = f"{w1['strike']:.2f},{corpo['strike']:.2f},{w2['strike']:.2f}"
        premios_str = f"{w1['premio_ask']:.4f},{corpo['premio_ask']:.4f},{w2['premio_ask']:.4f}"

        _stage(f"BWB_B {lado} — custo", n_pos_direcao, 1 if viavel else 0,
               f"K={strikes_str} custo={custo_total:.2f}" if viavel
               else f"custo={custo_total:.2f} > orcamento={orcamento:.2f}")

        logger.info(
            "BWB borboleta [%s]: viavel=%s strikes=%s custo=R$%.2f (%s%.0f%% orcamento)",
            lado, viavel, strikes_str, custo_total,
            "CREDITO " if custo_total < 0 else "",
            abs(custo_total) / max(orcamento, 0.01) * 100,
        )

        return {
            "strike": corpo["strike"] if viavel else None,
            "premio_ask": corpo["premio_ask"] if viavel else None,
            "qtd": qtd_lote if viavel else 0,
            "custo": round(custo_total, 2) if viavel else 0.0,
            "viavel": viavel,
            "strikes_bwb": strikes_str if viavel else None,
            "premios_bwb": premios_str if viavel else None,
            "custo_borboleta": round(custo_total, 2),
            "lotes_bwb": lotes,
        }
