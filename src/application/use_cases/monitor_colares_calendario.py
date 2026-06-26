import logging
import math
import time
from collections import defaultdict
from datetime import date
from typing import Optional

from src.domain.services.calculadora_colar_calendario import (
    CalculadoraColarCalendario,
    ResultadoColarCalendario,
)
from src.domain.services.market_data_source import FieldName
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient
from src.infrastructure.persistence.repositories.repositories import (
    DividendoRepository,
    InstrumentoRepository,
    ParametroRepository,
)

logger = logging.getLogger(__name__)


# Ordem dos filtros aplicados no varrer(). regras_dialog lê esta lista automaticamente.
FILTROS_COLLAR_CALENDARIO = [
    "1. Ativo (checklist)",
    "2. Vencimento",
    "3. Códigos (put e call)",
    "4. Dias até vencimento",
    "5. DTE (mín/máx)",
    "6. Strike (RTD)",
    "7. Preço (RTD OCP/OVD)",
    "8. Liquidez (QUL)",
]


class MonitorColaresCalendarioUseCase:

    _cache_iv_historico: dict[str, tuple[float, float, float]] = {}

    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self._calculadora = None

    def _get_calculadora(self) -> CalculadoraColarCalendario:
        if self._calculadora is None:
            param = self.param_repo.get_by_chave("taxa_cdi")
            taxa_cdi = param.valor if param else 0.1450
            premio_risco = self._get_param("premio_risco_colar_calendario", 1.2)
            emol = self._get_param("taxa_emolumento_pct", 0.00025)
            liq = self._get_param("taxa_liquidacao_pct", 0.000275)
            from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3
            ir = self._get_param("taxa_ir_pct", 0.15)
            custos_b3 = CalculadoraCustosB3(emol, liq, ir)
            limiar = self._get_param("limiar_classificacao_calendario", 0.15)
            be_mult = self._get_param("be_search_range_mult", 0.15)
            self._calculadora = CalculadoraColarCalendario(taxa_cdi, premio_risco=premio_risco, custos_b3=custos_b3, limiar_pct=limiar, be_range_mult=be_mult)
        return self._calculadora

    def _carregar_iv_historico(self, ativo: str) -> tuple[float, float, float] | None:
        if ativo in self._cache_iv_historico:
            return self._cache_iv_historico[ativo]
        try:
            client = OpcoesNetClient()
            hist = client.get_stock_history_formatted(ativo, 252)
            if not hist:
                return None
            valores = [c["vol_impl"] for c in hist if c.get("vol_impl") and c["vol_impl"] > 0]
            if len(valores) < 60:
                return None
            stats = (min(valores), max(valores), valores[-1])
            self._cache_iv_historico[ativo] = stats
            return stats
        except Exception:
            return None

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()
        self._cache_iv_historico.clear()

    def _get_param(self, chave: str, default: float) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def varrer(self, rtd, dados_mercado: dict | None = None, params: dict | None = None, ativos: list[str] | None = None, pipeline_tracker: PipelineTracker | None = None) -> list[ResultadoColarCalendario]:
        calc = self._get_calculadora()
        inst_map = self.inst_repo.get_all_mapped()
        ativos_set = set(ativos) if ativos else None

        defaults = {
            "dte_call_min": self._get_param("dte_call_min", 25),
            "dte_call_max": self._get_param("dte_call_max", 60),
            "dte_extra_min": self._get_param("dte_extra_min", 30),
            "dte_extra_max": self._get_param("dte_extra_max", 120),
            "dte_total_max": self._get_param("dte_total_max", 180),
            "qul_min_put": self._get_param("colar_qul_min_put", 100),
            "qul_min_call": self._get_param("colar_qul_min_call", 100),
        }
        if params is None:
            params = defaults
        else:
            for k, v in defaults.items():
                params.setdefault(k, v)

        hoje = date.today()
        calls_por_ativo: dict[str, list] = defaultdict(list)
        puts_por_ativo: dict[str, list] = defaultdict(list)
        stats = {"total": 0, "sem_vencimento": 0, "sem_codigos": 0, "sem_dias": 0, "sem_strike": 0, "sem_strike_registrado": 0, "sem_ocp_ovd": 0, "sem_ocp_registrado": 0, "sem_ovd_registrado": 0, "sem_preco": 0, "sem_qul": 0, "calls": 0, "puts": 0, "fora_dte": 0, "fora_ativo": 0}

        source = dados_mercado if dados_mercado else inst_map
        n_total = 0
        n_sem_inst = 0
        n_fora_ativo = 0
        n_sem_venc = 0
        n_sem_cod = 0
        n_sem_dias = 0
        n_fora_dte = 0
        n_sem_strike = 0
        n_sem_preco = 0
        n_sem_qul = 0
        n_passaram = 0
        _t_pre = time.perf_counter()

        for key in source:
            stats["total"] += 1
            n_total += 1
            dm = dados_mercado.get(key) if dados_mercado else None
            if dados_mercado:
                ativo_k, cod_put_k = key.split("|", 1)
                inst = inst_map.get((ativo_k, cod_put_k))
            else:
                inst = inst_map.get(key)
            if not inst:
                n_sem_inst += 1
                continue

            if ativos_set and inst.ativo not in ativos_set:
                stats["fora_ativo"] += 1
                n_fora_ativo += 1
                continue

            if not inst.vencimento or inst.vencimento <= hoje:
                stats["sem_vencimento"] += 1
                n_sem_venc += 1
                continue
            if not inst.cod_put or not inst.cod_call:
                stats["sem_codigos"] += 1
                n_sem_cod += 1
                continue
            if inst.dias_ate_vencimento is None or inst.dias_ate_vencimento <= 0:
                stats["sem_dias"] += 1
                n_sem_dias += 1
                continue

            dte = inst.dias_ate_vencimento
            if dte < params["dte_call_min"] or dte > params["dte_total_max"]:
                stats["fora_dte"] += 1
                n_fora_dte += 1
                continue

            if dm:
                strike = dm.get("strike_rtd")
                preco_call = dm.get("of_compra_call") or 0.0
                preco_put = dm.get("of_venda_put") or 0.0
                qul_put = dm.get("qul_put") or 0
                qul_call = dm.get("qul_call") or 0
            else:
                strike = rtd.ler_campo_cache(inst.cod_put, FieldName.STRIKE)
                if not strike or strike <= 0:
                    strike = rtd.ler_campo_cache(inst.cod_call, FieldName.STRIKE)
                ocp = rtd.ler_campo_cache(inst.cod_call, FieldName.BID)
                ovd = rtd.ler_campo_cache(inst.cod_put, FieldName.ASK)
                preco_call = ocp or 0.0
                preco_put = ovd or 0.0
                qul_put = rtd.ler_campo_cache(inst.cod_put, FieldName.QTD_LAST) or 0
                qul_call = rtd.ler_campo_cache(inst.cod_call, FieldName.QTD_LAST) or 0

            if not strike or strike <= 0:
                stats["sem_strike"] += 1
                n_sem_strike += 1
                continue
            if preco_call <= 0 or preco_put <= 0:
                stats["sem_preco"] += 1
                n_sem_preco += 1
                continue

            qul_min_put = params.get("qul_min_put", 100)
            qul_min_call = params.get("qul_min_call", 100)
            if qul_put <= 0 and qul_call <= 0:
                stats["sem_qul"] += 1
                n_sem_qul += 1
                continue
            if (qul_put > 0 and qul_put < qul_min_put) or (qul_call > 0 and qul_call < qul_min_call):
                stats["sem_qul"] += 1
                n_sem_qul += 1
                continue

            n_passaram += 1
            dados = {
                "strike": strike,
                "cod_call": inst.cod_call,
                "cod_put": inst.cod_put,
                "vencimento": inst.vencimento,
                "dte": dte,
                "preco_call": preco_call,
                "preco_put": preco_put,
            }

            if dte <= params["dte_call_max"]:
                calls_por_ativo[inst.ativo].append(dados)
                stats["calls"] += 1
            else:
                puts_por_ativo[inst.ativo].append(dados)
                stats["puts"] += 1

        if pipeline_tracker is not None:
            pipeline_tracker.nome_estrategia = "COLLAR_CALENDARIO"
            tempo_pre = time.perf_counter() - _t_pre
            pipeline_tracker.add_stage("1. Ativo válido", n_total, n_total - n_sem_inst,
                "Instrumento não encontrado no banco (instância None)",
                tempo_s=tempo_pre)
            pipeline_tracker.add_stage("2. Ativo (checklist)", n_total - n_sem_inst, n_total - n_sem_inst - n_fora_ativo,
                "Ativo não está na check-list ou whitelist configurada em Parâmetros > COLLAR_CALENDARIO",
                tempo_s=0.0)
            pipeline_tracker.add_stage("3. Vencimento", n_total - n_sem_inst - n_fora_ativo, n_total - n_sem_inst - n_fora_ativo - n_sem_venc,
                "Sem vencimento futuro — opção já venceu ou data inválida",
                tempo_s=0.0)
            pipeline_tracker.add_stage("4. Códigos", n_total - n_sem_inst - n_fora_ativo - n_sem_venc, n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod,
                "Código do PUT ou CALL não cadastrado no banco (instrumentos_base)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("5. Dias (DTE)", n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod, n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod - n_sem_dias,
                "dias_ate_vencimento inválido ou <= 0 (RTD não retornou DTE)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("6. DTE (mín/máx)", n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod - n_sem_dias, n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod - n_sem_dias - n_fora_dte,
                f"Fora da faixa DTE call={params['dte_call_min']}–{params['dte_call_max']}d ou total >{params['dte_total_max']}d (Parâmetros > COLLAR_CALENDARIO)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("7. Strike (RTD)", n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod - n_sem_dias - n_fora_dte, n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod - n_sem_dias - n_fora_dte - n_sem_strike,
                "Strike não disponível no RTD (PEX zerado ou cache não populado)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("8. Preço (RTD)", n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod - n_sem_dias - n_fora_dte - n_sem_strike, n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod - n_sem_dias - n_fora_dte - n_sem_strike - n_sem_preco,
                "OCP (call) ou OVD (put) zerado no RTD — sem oferta de compra/venda",
                tempo_s=0.0)
            pipeline_tracker.add_stage("9. Liquidez (QUL)", n_total - n_sem_inst - n_fora_ativo - n_sem_venc - n_sem_cod - n_sem_dias - n_fora_dte - n_sem_strike - n_sem_preco, n_passaram,
                f"QUL abaixo do mínimo configurado (put≥{params.get('qul_min_put',100)} call≥{params.get('qul_min_call',100)}) em Parâmetros > COLLAR_CALENDARIO",
                tempo_s=0.0)
            logger.info("PipelineTracker (%s): %d -> %d", pipeline_tracker.nome_estrategia, n_total, n_passaram)
            self._ultimo_pipeline = pipeline_tracker

        if "PETR4" in calls_por_ativo or "PETR4" in puts_por_ativo:
            logger.debug("CollarCal PETR4: calls=%d puts=%d",
                         len(calls_por_ativo.get("PETR4", [])),
                         len(puts_por_ativo.get("PETR4", [])))
            if "PETR4" in calls_por_ativo:
                for c in calls_por_ativo["PETR4"]:
                    logger.debug("CollarCal PETR4 call: %s strike=%.2f dte=%d ocp=%.4f",
                                 c["cod_call"], c["strike"], c["dte"], c["preco_call"])
            if "PETR4" in puts_por_ativo:
                for c in puts_por_ativo["PETR4"]:
                    logger.debug("CollarCal PETR4 put: %s strike=%.2f dte=%d ovd=%.4f",
                                 c["cod_put"], c["strike"], c["dte"], c["preco_put"])

        resultados = []
        _cache_dividendos_por_ativo: dict[str, list[tuple[date, float]]] = {}
        c_pares = c_calc_ok = c_viaveis = c_filtro_dist = c_filtro_dte = 0
        c_ativos_com_dados = 0

        _t_pares = time.perf_counter()

        for ativo in calls_por_ativo:
            if ativo not in puts_por_ativo:
                continue

            calls = calls_por_ativo[ativo]
            puts = puts_por_ativo[ativo]

            preco_ativo = 0.0
            preco_compra_ativo = 0.0
            if dados_mercado:
                for key, dm_item in dados_mercado.items():
                    ativo_k, cod_put_k = key.split("|", 1)
                    if ativo_k == ativo:
                        preco_ativo = dm_item.get("preco_ativo") or 0.0
                        preco_compra_ativo = dm_item.get("of_venda_ativo") or 0.0
                        break
            if preco_ativo <= 0:
                preco_ativo = rtd.ler_campo_cache(ativo, FieldName.ASK) or 0.0
                if preco_ativo <= 0:
                    continue
                of_venda_ativo = rtd.ler_campo_cache(ativo, FieldName.ASK)
                preco_compra_ativo = of_venda_ativo if (of_venda_ativo and of_venda_ativo > 0) else 0.0

            c_ativos_com_dados += 1

            if ativo not in _cache_dividendos_por_ativo:
                divs = DividendoRepository(self.db_path).get_by_ativo(ativo)
                divs_futuros = []
                for d in divs:
                    data_ex = d.get("data_ex") or d.get("data_com")
                    valor = d.get("valor")
                    if data_ex and valor and valor > 0:
                        try:
                            dex = date.fromisoformat(str(data_ex))
                            if dex > date.today():
                                divs_futuros.append((dex, valor))
                        except (ValueError, TypeError):
                            pass
                _cache_dividendos_por_ativo[ativo] = divs_futuros
            dividendos_ativo = _cache_dividendos_por_ativo.get(ativo) or []

            iv_hist = self._carregar_iv_historico(ativo)
            iv_hist_min = iv_hist[0] if iv_hist else None
            iv_hist_max = iv_hist[1] if iv_hist else None

            cal_diff_max = params.get("calendario_strike_diff_max")
            if cal_diff_max is None:
                cal_diff_max = self._get_param("calendario_strike_diff_max", 2)
            cal_diff_max = int(cal_diff_max)
            todos_strikes = sorted(set(c["strike"] for c in calls) | set(p["strike"] for p in puts))
            strike_interval = min(b - a for a, b in zip(todos_strikes, todos_strikes[1:])) if len(todos_strikes) > 1 else 0.5
            strike_diff_max = strike_interval * cal_diff_max

            calls_ordenadas = sorted(
                calls,
                key=lambda c: abs(c["strike"] - preco_ativo),
            )

            viaveis_por_call: dict[str, int] = {}
            for call in calls_ordenadas:
                sc = call["strike"]
                dte_call = call["dte"]

                # Pares ordenados por proximidade de strike com a call
                puts_ordenadas = sorted(
                    puts,
                    key=lambda p: abs(p["strike"] - sc),
                )

                for put in puts_ordenadas:
                    sp = put["strike"]
                    if abs(sp - sc) > strike_diff_max:
                        c_filtro_dist += 1
                        continue
                    dte_extra = put["dte"] - dte_call

                    if dte_extra < params["dte_extra_min"] or dte_extra > params["dte_extra_max"]:
                        c_filtro_dte += 1
                        continue

                    c_pares += 1

                    resultado = calc.calcular(
                        preco_ativo=preco_ativo,
                        strike_call=sc,
                        strike_put=sp,
                        premio_call=call["preco_call"],
                        premio_put=put["preco_put"],
                        cod_call=call["cod_call"],
                        cod_put=put["cod_put"],
                        dte_call=dte_call,
                        dte_put=put["dte"],
                        ativo=ativo,
                        vencimento_call=call["vencimento"],
                        vencimento_put=put["vencimento"],
                        preco_compra_ativo=preco_compra_ativo,
                        dividendos=dividendos_ativo,
                        iv_hist_min=iv_hist_min,
                        iv_hist_max=iv_hist_max,
                    )

                    if resultado:
                        resultados.append(resultado)
                        c_calc_ok += 1
                        if resultado.viavel:
                            c_viaveis += 1
                            logger.debug("CollarCal PAR VIÁVEL %s: call=%s(%.0f) put=%s(%.0f) DTE %d+%d |ΔK|=%.1f pct_cdi=%.2f",
                                         ativo, call["cod_call"], sc, put["cod_put"], sp,
                                         dte_call, dte_extra, abs(sc - sp), resultado.pct_cdi)
                            viaveis_por_call[call["cod_call"]] = viaveis_por_call.get(call["cod_call"], 0) + 1
                            if viaveis_por_call.get(call["cod_call"], 0) >= 3:
                                break  # top-3 puts por call

        if pipeline_tracker is not None:
            tempo_pares = time.perf_counter() - _t_pares
            pipeline_tracker.add_stage("10. Ativos com dados", c_ativos_com_dados, c_ativos_com_dados,
                "Ativos com preço e OVD disponíveis",
                tempo_s=tempo_pares)
            pipeline_tracker.add_stage("11. Pares (strike+DTE)", c_pares + c_filtro_dist + c_filtro_dte, c_pares,
                f"{c_filtro_dist} fora da distância de strike, {c_filtro_dte} fora do DTE extra",
                tempo_s=0.0)
            pipeline_tracker.add_stage("12. Cálculo viabilidade", c_pares, c_calc_ok,
                f"{c_pares - c_calc_ok} pares inviáveis (prêmio-risco, B3, dividendos, etc.)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("13. Resultado final", c_calc_ok, c_viaveis,
                f"{c_viaveis} viáveis no monitor",
                tempo_s=0.0)
            self._ultimo_pipeline = pipeline_tracker

        if not resultados:
            logger.warning("CollarCal STATS: %s", stats)
            return []

        resultados = [r for r in resultados if r.viavel]
        if not resultados:
            return []

        # ── Score de Ranking (ordenacao multicriterio) ──
        peso_theta = self._get_param("ranking_peso_theta", 3.0)
        peso_cdi = self._get_param("ranking_peso_cdi", 2.0)
        peso_sigma = self._get_param("ranking_peso_sigma", 2.0)
        peso_credito = self._get_param("ranking_peso_credito", 1.0)
        peso_liquidez = self._get_param("ranking_peso_liquidez", 0.5)

        def _sigma_folga(r):
            if r.iv_call <= 0 or r.iv_put <= 0 or r.dte_call <= 0 or r.preco_ativo <= 0:
                return 0.0
            iv_media = (r.iv_call + r.iv_put) / 2 / 100
            sigma_diario = iv_media / math.sqrt(252)
            sigma_periodo = sigma_diario * math.sqrt(r.dte_call)
            if sigma_periodo <= 0:
                return 0.0
            folga = min(abs(r.preco_ativo - r.strike_call), abs(r.preco_ativo - r.strike_put))
            return folga / (r.preco_ativo * sigma_periodo)

        raw = []
        for r in resultados:
            cap_base = abs(r.capital_empregado) if r.capital_empregado <= 0 else r.capital_empregado
            credito_ratio = max(0, r.net_credito / cap_base) if cap_base > 0 else 0.0
            raw.append({
                "theta": abs(r.theta_liquido),
                "cdi": r.pct_cdi,
                "sigma": _sigma_folga(r),
                "credito": credito_ratio,
                "liquidez": 1.0,
            })

        max_theta = max(x["theta"] for x in raw) or 1.0
        max_cdi = max(x["cdi"] for x in raw) or 1.0
        max_sigma = max(x["sigma"] for x in raw) or 1.0
        max_credito = max(x["credito"] for x in raw) or 1.0

        for r, d in zip(resultados, raw):
            t_norm = d["theta"] / max_theta
            c_norm = d["cdi"] / max_cdi
            s_norm = d["sigma"] / max_sigma
            cr_norm = d["credito"] / max_credito
            r.score = round(
                peso_theta * t_norm
                + peso_cdi * c_norm
                + peso_sigma * s_norm
                + peso_credito * cr_norm
                + peso_liquidez * d["liquidez"],
                4,
            )

        # ── Score IV (alternativo com pesos recalibrados) ──
        peso_iv_rank = self._get_param("ranking_peso_iv_rank", 25.0) / 100.0
        peso_dist = self._get_param("ranking_peso_dist_strike", 25.0) / 100.0
        peso_theta_margin = self._get_param("ranking_peso_theta_margin", 25.0) / 100.0
        peso_vega = self._get_param("ranking_peso_vega", 10.0) / 100.0
        peso_liquidez_iv = self._get_param("ranking_peso_liquidez_iv", 10.0) / 100.0
        peso_risco_max = self._get_param("ranking_peso_risco_max", 5.0) / 100.0

        raw_iv = []
        for r in resultados:
            iv_rank_norm = min(r.iv_rank / 100.0, 1.0) if r.iv_rank else 0.0
            strike_menor = min(r.strike_call, r.strike_put)
            dist_norm = max(0.0, (strike_menor - r.capital_empregado) / strike_menor) if strike_menor > 0 else 0.0
            theta_m = abs(r.theta_liquido) / max(r.capital_empregado, 1) * 1000
            vega_n = max(r.vega_liquido, 0) / 100
            liq_n = 0.5
            risco_n = 1.0 - min(r.risco_max / strike_menor, 1.0) if strike_menor > 0 else 0.0
            raw_iv.append({
                "iv_rank": iv_rank_norm,
                "dist": dist_norm,
                "theta": theta_m,
                "vega": vega_n,
                "liq": liq_n,
                "risco": risco_n,
            })

        max_iv = max(x["iv_rank"] for x in raw_iv) or 1.0
        max_dist = max(x["dist"] for x in raw_iv) or 1.0
        max_theta = max(x["theta"] for x in raw_iv) or 1.0
        max_vega = max(x["vega"] for x in raw_iv) or 1.0
        max_liq = max(x["liq"] for x in raw_iv) or 1.0
        max_risco = max(x["risco"] for x in raw_iv) or 1.0

        for r, d in zip(resultados, raw_iv):
            r.score_iv = round(
                peso_iv_rank * (d["iv_rank"] / max_iv)
                + peso_dist * (d["dist"] / max_dist)
                + peso_theta_margin * (d["theta"] / max_theta)
                + peso_vega * (d["vega"] / max_vega)
                + peso_liquidez_iv * (d["liq"] / max_liq)
                + peso_risco_max * (d["risco"] / max_risco),
                4,
            )

        resultados.sort(key=lambda r: -r.score)
        logger.warning("CollarCal STATS: %s", stats)
        logger.warning("CollarCal TOTAL: %d viaveis em %d ativos", len(resultados), len(set(r.ativo for r in resultados)))
        return resultados
