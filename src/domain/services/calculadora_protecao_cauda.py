from dataclasses import dataclass
import logging

from src.domain.services.calculadora_cauda_assincrona import ResultadoCaudaAssincrona

logger = logging.getLogger(__name__)


_LOTE = 100


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


class CalculadoraProtecaoCauda:
    """Camada de proteção via asa quebrada (BWB) sobre Collar Calendário otimizado por ratio.

    DEPOIS que uma variante de ResultadoCaudaAssincrona já foi escolhida,
    avalia se/como proteger a exposição naked comprando opções mais OTM.
    """

    NAKED_FRAC_MINIMO = 0.02

    @staticmethod
    def avaliar(
        resultado: ResultadoCaudaAssincrona,
        strikes_call_candidatos: list[dict] | None = None,
        strikes_put_candidatos: list[dict] | None = None,
        qtd_acao: int = 100,
        n_sigma: float = 2.0,
        limite_protecao_pct: float = 0.35,
        calda_preco_min_opcao: float = 0.01,
        cab_minimo: int = 1,
        fator_seguranca_liquidez: float = 0.2,
    ) -> ResultadoProtecaoCauda | None:
        naked_call_frac = max(0.0, resultado.ratio_call - 1.0)
        naked_put_gap = max(0.0, 1.0 - resultado.ratio_put)

        if (
            naked_call_frac < CalculadoraProtecaoCauda.NAKED_FRAC_MINIMO
            and naked_put_gap < CalculadoraProtecaoCauda.NAKED_FRAC_MINIMO
        ):
            return None

        ganho_extra_ratio = resultado.pnl_com_ratio - resultado.pnl_base

        s_target_call = resultado.preco_ativo * (1.0 + n_sigma * resultado.sigma_periodo)
        s_target_put = resultado.preco_ativo * (1.0 - n_sigma * resultado.sigma_periodo)

        info_call = CalculadoraProtecaoCauda._avaliar_lado(
            lado="call",
            naked_frac=naked_call_frac,
            strikes_candidatos=strikes_call_candidatos or [],
            s_target=s_target_call,
            acima_do_target=True,
            qtd_acao=qtd_acao,
            ganho_extra_ratio=ganho_extra_ratio,
            limite_protecao_pct=limite_protecao_pct,
            calda_preco_min_opcao=calda_preco_min_opcao,
            cab_minimo=cab_minimo,
            fator_seguranca_liquidez=fator_seguranca_liquidez,
        )

        info_put = CalculadoraProtecaoCauda._avaliar_lado(
            lado="put",
            naked_frac=naked_put_gap,
            strikes_candidatos=strikes_put_candidatos or [],
            s_target=s_target_put,
            acima_do_target=False,
            qtd_acao=qtd_acao,
            ganho_extra_ratio=ganho_extra_ratio,
            limite_protecao_pct=limite_protecao_pct,
            calda_preco_min_opcao=calda_preco_min_opcao,
            cab_minimo=cab_minimo,
            fator_seguranca_liquidez=fator_seguranca_liquidez,
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

        return ResultadoProtecaoCauda(
            id_chassi=resultado.id_chassi,
            ativo=resultado.ativo,
            lado_protegido=lado_protegido,
            naked_call_frac=naked_call_frac,
            naked_put_gap=naked_put_gap,
            strike_protecao_call=info_call["strike"],
            strike_protecao_put=info_put["strike"],
            premio_ask_call=info_call["premio_ask"],
            premio_ask_put=info_put["premio_ask"],
            qtd_protecao_call=info_call["qtd"],
            qtd_protecao_put=info_put["qtd"],
            custo_protecao_call=info_call["custo"],
            custo_protecao_put=info_put["custo"],
            custo_protecao_total=round(custo_total, 2),
            pnl_sem_protecao=resultado.pnl_com_ratio,
            pnl_liquido_pos_protecao=round(pnl_liquido, 2),
            viavel_call=info_call["viavel"],
            viavel_put=info_put["viavel"],
            viavel=info_call["viavel"] or info_put["viavel"],
        )

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
    ) -> dict:
        n_entrada = len(strikes_candidatos) if strikes_candidatos else 0
        if naked_frac < CalculadoraProtecaoCauda.NAKED_FRAC_MINIMO or not strikes_candidatos:
            if n_entrada == 0:
                logger.debug("BWB _avaliar_lado [%s]: 0 strikes na entrada — sem candidatos", lado)
            return {
                "strike": None, "premio_ask": None, "qtd": 0, "custo": 0.0, "viavel": False,
            }

        qtd_bruta = naked_frac * qtd_acao
        qtd_lote = max(1, int(qtd_bruta / _LOTE + 0.5)) * _LOTE

        limite_liquidez = max(cab_minimo, qtd_lote * fator_seguranca_liquidez)

        filtrados = [
            s for s in strikes_candidatos
            if (
                min(s.get("vol_ask", 0) or 0, s.get("vol_bid", 0) or 0)
            ) >= limite_liquidez
            and (s.get("premio_ask", 0) or 0) >= calda_preco_min_opcao
            and (s.get("strike") or 0) > 0
        ]
        n_pos_liquidez = len(filtrados)

        if n_pos_liquidez == 0:
            logger.debug(
                "BWB _avaliar_lado [%s]: %d candidatos na entrada, 0 passaram liquidez "
                "(limite=%.0f, preco_min=%.4f)",
                lado, n_entrada, limite_liquidez, calda_preco_min_opcao,
            )
            return {
                "strike": None, "premio_ask": None, "qtd": 0, "custo": 0.0, "viavel": False,
            }

        if acima_do_target:
            filtrados = [s for s in filtrados if s["strike"] >= s_target]
        else:
            filtrados = [s for s in filtrados if s["strike"] <= s_target]
        n_pos_direcao = len(filtrados)

        if n_pos_direcao == 0:
            logger.debug(
                "BWB _avaliar_lado [%s]: %d passaram liquidez, 0 passaram direcao "
                "(target=%.2f, %s)",
                lado, n_pos_liquidez, s_target,
                "strike >= target" if acima_do_target else "strike <= target",
            )
            return {
                "strike": None, "premio_ask": None, "qtd": 0, "custo": 0.0, "viavel": False,
            }

        if acima_do_target:
            escolha = min(filtrados, key=lambda s: abs(s["strike"] - s_target))
        else:
            escolha = min(filtrados, key=lambda s: abs(s["strike"] - s_target))

        premio_ask = escolha.get("premio_ask", 0) or 0
        custo = premio_ask * qtd_lote

        viavel = ganho_extra_ratio > 0 and custo <= ganho_extra_ratio * limite_protecao_pct

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
        }
