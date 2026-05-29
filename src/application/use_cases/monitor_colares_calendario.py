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
            self._calculadora = CalculadoraColarCalendario(taxa_cdi, premio_risco=premio_risco)
        return self._calculadora

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()

    def _get_param(self, chave: str, default: float) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def varrer(self, rtd, params: dict | None = None, ativos: list[str] | None = None) -> list[ResultadoColarCalendario]:
        calc = self._get_calculadora()
        inst_map = self.inst_repo.get_all_mapped()
        ativos_set = set(ativos) if ativos else None

        if params is None:
            params = {
                "dte_call_min": 29,
                "dte_call_max": 60,
                "dte_extra_min": 30,
                "dte_extra_max": 90,
                "dte_total_max": 120,
            }

        hoje = date.today()
        calls_por_ativo: dict[str, list] = defaultdict(list)
        puts_por_ativo: dict[str, list] = defaultdict(list)
        stats = {"total": 0, "sem_vencimento": 0, "sem_codigos": 0, "sem_dias": 0, "sem_strike": 0, "sem_strike_registrado": 0, "sem_ocp_ovd": 0, "sem_ocp_registrado": 0, "sem_ovd_registrado": 0, "sem_preco": 0, "sem_qul": 0, "calls": 0, "puts": 0, "fora_dte": 0, "fora_ativo": 0}

        for key, inst in inst_map.items():
            stats["total"] += 1
            if not inst.vencimento or inst.vencimento <= hoje:
                stats["sem_vencimento"] += 1
                continue
            if not inst.cod_put or not inst.cod_call:
                stats["sem_codigos"] += 1
                continue
            if inst.dias_ate_vencimento is None or inst.dias_ate_vencimento <= 0:
                stats["sem_dias"] += 1
                continue

            # ---- FILTRO 1: ATIVOS SELECIONADOS (mais barato) ----
            if ativos_set and inst.ativo not in ativos_set:
                stats["fora_ativo"] += 1
                continue

            # ---- FILTRO 2: DTE (barato, sem RTD) ----
            dte = inst.dias_ate_vencimento
            if dte < params["dte_call_min"] or dte > params["dte_total_max"]:
                stats["fora_dte"] += 1
                continue

            # ---- FILTRO 3: LIQUIDEZ (RTD Onda 2 + QUL) ----
            strike = rtd.ler_campo_cache(inst.cod_put, "PEX")
            if not strike or strike <= 0:
                strike = rtd.ler_campo_cache(inst.cod_call, "PEX")
            if not strike or strike <= 0:
                chk_reg = rtd._topic_map.get(f"{inst.cod_put}|PEX")
                if chk_reg is None:
                    chk_reg = rtd._topic_map.get(f"{inst.cod_call}|PEX")
                stats["sem_strike"] += 1
                if chk_reg is not None:
                    stats["sem_strike_registrado"] += 1
                continue

            ocp = rtd.ler_campo_cache(inst.cod_call, "OCP")
            ovd = rtd.ler_campo_cache(inst.cod_put, "OVD")
            if ocp is None or ovd is None:
                chk_ocp = rtd._topic_map.get(f"{inst.cod_call}|OCP")
                chk_ovd = rtd._topic_map.get(f"{inst.cod_put}|OVD")
                if chk_ocp is not None:
                    stats["sem_ocp_registrado"] += 1
                if chk_ovd is not None:
                    stats["sem_ovd_registrado"] += 1
                stats["sem_ocp_ovd"] += 1
                continue

            preco_call = ocp or 0.0
            preco_put = ovd or 0.0
            if preco_call <= 0 or preco_put <= 0:
                stats["sem_preco"] += 1
                continue

            qul_put = rtd.ler_campo_cache(inst.cod_put, "QUL") or 0
            qul_call = rtd.ler_campo_cache(inst.cod_call, "QUL") or 0
            if qul_put <= 0 and qul_call <= 0:
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

            preco_ativo = rtd.ler_campo_cache(ativo, "ULT") or 0.0
            if preco_ativo <= 0:
                continue

            of_venda_ativo = rtd.ler_campo_cache(ativo, "OVD")
            preco_compra_ativo = of_venda_ativo if (of_venda_ativo and of_venda_ativo > 0) else preco_ativo

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

            cal_diff_pct = params.get("calendario_strike_diff_pct")
            if cal_diff_pct is None:
                cal_diff_pct = self._get_param("calendario_strike_diff_pct", 0.03)
            strike_diff_max = preco_ativo * cal_diff_pct

            call_otm_max = params.get("calendario_call_otm_max")
            if call_otm_max is None:
                call_otm_max = self._get_param("calendario_call_otm_max", 0.04)
            call_otm_limite = preco_ativo * (1 + call_otm_max)

            calls_otm = [c for c in calls if c["strike"] > preco_ativo and c["strike"] <= call_otm_limite]
            calls_otm.sort(key=lambda c: c["strike"] - preco_ativo)

            for call in calls_otm:
                sc = call["strike"]
                dte_call = call["dte"]

                # Filtra puts OTM (strike < spot) e ordena por |strike_call - strike_put|
                puts_otm = [p for p in puts if p["strike"] < preco_ativo]
                puts_ordenadas = sorted(
                    puts_otm,
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

                    if resultado and resultado.viavel:
                        resultados.append(resultado)
                        logger.debug("CollarCal PAR VIÁVEL %s: call=%s(%.0f) put=%s(%.0f) DTE %d+%d |ΔK|=%.1f pct_cdi=%.2f",
                                     ativo, call["cod_call"], sc, put["cod_put"], sp,
                                     dte_call, dte_extra, abs(sc - sp), resultado.pct_cdi)
                        break  # melhor par pra esta call

        resultados.sort(key=lambda r: -r.pct_cdi)
        logger.debug("CollarCal STATS: %s", stats)
        logger.debug("CollarCal TOTAL: %d viaveis em %d ativos", len(resultados), len(set(r.ativo for r in resultados)))
        return resultados
