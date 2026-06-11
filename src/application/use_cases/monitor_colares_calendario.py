import logging
from collections import defaultdict
from datetime import date
from typing import Optional

from src.domain.services.calculadora_colar_calendario import (
    CalculadoraColarCalendario,
    ResultadoColarCalendario,
)
from src.infrastructure.persistence.repositories.repositories import (
    DividendoRepository,
    InstrumentoRepository,
    ParametroRepository,
)

logger = logging.getLogger(__name__)


class MonitorColaresCalendarioUseCase:

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

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()

    def _get_param(self, chave: str, default: float) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def varrer(self, rtd, dados_mercado: dict | None = None, params: dict | None = None, ativos: list[str] | None = None) -> list[ResultadoColarCalendario]:
        calc = self._get_calculadora()
        inst_map = self.inst_repo.get_all_mapped()
        ativos_set = set(ativos) if ativos else None

        defaults = {
            "dte_call_min": self._get_param("dte_call_min", 29),
            "dte_call_max": self._get_param("dte_call_max", 60),
            "dte_extra_min": self._get_param("dte_extra_min", 30),
            "dte_extra_max": self._get_param("dte_extra_max", 90),
            "dte_total_max": self._get_param("dte_total_max", 120),
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
        for key in source:
            stats["total"] += 1
            dm = dados_mercado.get(key) if dados_mercado else None
            inst = inst_map.get(key)
            if not inst:
                continue
            if not inst.vencimento or inst.vencimento <= hoje:
                stats["sem_vencimento"] += 1
                continue
            if not inst.cod_put or not inst.cod_call:
                stats["sem_codigos"] += 1
                continue
            if inst.dias_ate_vencimento is None or inst.dias_ate_vencimento <= 0:
                stats["sem_dias"] += 1
                continue

            if ativos_set and inst.ativo not in ativos_set:
                stats["fora_ativo"] += 1
                continue

            dte = inst.dias_ate_vencimento
            if dte < params["dte_call_min"] or dte > params["dte_total_max"]:
                stats["fora_dte"] += 1
                continue

            # ---- FILTRO 3: LIQUIDEZ (dados_mercado > RTD cache) ----
            if dm:
                strike = dm.get("strike_rtd")
                preco_call = dm.get("of_compra_call") or 0.0
                preco_put = dm.get("of_venda_put") or 0.0
                qul_put = dm.get("qul_put") or 0
                qul_call = dm.get("qul_call") or 0
            else:
                strike = rtd.ler_campo_cache(inst.cod_put, "PEX")
                if not strike or strike <= 0:
                    strike = rtd.ler_campo_cache(inst.cod_call, "PEX")
                ocp = rtd.ler_campo_cache(inst.cod_call, "OCP")
                ovd = rtd.ler_campo_cache(inst.cod_put, "OVD")
                preco_call = ocp or 0.0
                preco_put = ovd or 0.0
                qul_put = rtd.ler_campo_cache(inst.cod_put, "QUL") or 0
                qul_call = rtd.ler_campo_cache(inst.cod_call, "QUL") or 0

            if not strike or strike <= 0:
                stats["sem_strike"] += 1
                continue
            if preco_call <= 0 or preco_put <= 0:
                stats["sem_preco"] += 1
                continue

            qul_min_put = params.get("qul_min_put", 100)
            qul_min_call = params.get("qul_min_call", 100)
            if (qul_put > 0 or qul_call > 0) and (qul_put < qul_min_put or qul_call < qul_min_call):
                stats["sem_qul"] += 1
                continue

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

        for ativo in calls_por_ativo:
            if ativo not in puts_por_ativo:
                continue

            calls = calls_por_ativo[ativo]
            puts = puts_por_ativo[ativo]

            preco_ativo = 0.0
            preco_compra_ativo = 0.0
            if dados_mercado:
                for key, dm_item in dados_mercado.items():
                    inst2 = inst_map.get(key)
                    if inst2 and inst2.ativo == ativo:
                        preco_ativo = dm_item.get("preco_ativo") or 0.0
                        preco_compra_ativo = dm_item.get("of_venda_ativo") or 0.0
                        break
            if preco_ativo <= 0:
                preco_ativo = rtd.ler_campo_cache(ativo, "ULT") or 0.0
                if preco_ativo <= 0:
                    continue
                of_venda_ativo = rtd.ler_campo_cache(ativo, "OVD")
                preco_compra_ativo = of_venda_ativo if (of_venda_ativo and of_venda_ativo > 0) else 0.0

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
                        continue
                    dte_extra = put["dte"] - dte_call

                    if dte_extra < params["dte_extra_min"] or dte_extra > params["dte_extra_max"]:
                        continue

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
                    )

                    if resultado:
                        resultados.append(resultado)
                        if resultado.viavel:
                            logger.debug("CollarCal PAR VIÁVEL %s: call=%s(%.0f) put=%s(%.0f) DTE %d+%d |ΔK|=%.1f pct_cdi=%.2f",
                                         ativo, call["cod_call"], sc, put["cod_put"], sp,
                                         dte_call, dte_extra, abs(sc - sp), resultado.pct_cdi)
                            break  # melhor par pra esta call

        resultados.sort(key=lambda r: -r.pct_cdi)
        logger.warning("CollarCal STATS: %s", stats)
        logger.warning("CollarCal TOTAL: %d viaveis em %d ativos", len(resultados), len(set(r.ativo for r in resultados)))
        return [r for r in resultados if r.viavel]
