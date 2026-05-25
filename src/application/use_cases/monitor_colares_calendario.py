import logging
from collections import defaultdict
from datetime import date
from typing import Optional

from src.domain.services.calculadora_colar_calendario import (
    CalculadoraColarCalendario,
    ResultadoColarCalendario,
)
from src.infrastructure.persistence.repositories.repositories import (
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
            self._calculadora = CalculadoraColarCalendario(taxa_cdi, premio_risco=0.0)
        return self._calculadora

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()

    def varrer(self, rtd, params: dict | None = None, ativos: list[str] | None = None) -> list[ResultadoColarCalendario]:
        calc = self._get_calculadora()
        inst_map = self.inst_repo.get_all_mapped()
        ativos_set = set(ativos) if ativos else None

        if params is None:
            params = {
                "dte_call_min": 40,
                "dte_call_max": 60,
                "dte_extra_min": 30,
                "dte_extra_max": 90,
                "dte_total_max": 120,
            }

        hoje = date.today()
        calls_por_ativo: dict[str, list] = defaultdict(list)
        puts_por_ativo: dict[str, list] = defaultdict(list)
        stats = {"total": 0, "sem_strike": 0, "sem_ocp_ovd": 0, "sem_preco": 0, "calls": 0, "puts": 0}
        ativo_counts: dict[str, dict] = defaultdict(lambda: {"dte_range": 0, "strike_ok": 0, "ocp_ovd_ok": 0, "final": 0})

        for key, inst in inst_map.items():
            if not inst.vencimento or inst.vencimento <= hoje:
                continue
            if not inst.cod_put or not inst.cod_call:
                continue
            if inst.dias_ate_vencimento is None or inst.dias_ate_vencimento <= 0:
                continue

            dte = inst.dias_ate_vencimento
            if dte < params["dte_call_min"] or dte > params["dte_total_max"]:
                continue

            if ativos_set and inst.ativo not in ativos_set:
                continue

            # Só processa instrumentos com dados RTD disponíveis (Onda 2 já promoveu)
            strike = rtd.ler_campo_cache(inst.cod_put, "PEX")
            if not strike or strike <= 0:
                strike = rtd.ler_campo_cache(inst.cod_call, "PEX")
            if not strike or strike <= 0:
                stats["sem_strike"] += 1
                continue

            ocp = rtd.ler_campo_cache(inst.cod_call, "OCP")
            ovd = rtd.ler_campo_cache(inst.cod_put, "OVD")
            if ocp is None or ovd is None:
                stats["sem_ocp_ovd"] += 1
                continue

            preco_call = ocp or 0.0
            preco_put = ovd or 0.0
            if preco_call <= 0 or preco_put <= 0:
                stats["sem_preco"] += 1
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
            ac["final"] += 1

        logger.debug("CollarCal stats: total=%d calls=%d puts=%d sem_strike=%d sem_ocp_ovd=%d sem_preco=%d",
                     stats["total"], stats["calls"], stats["puts"],
                     stats["sem_strike"], stats["sem_ocp_ovd"], stats["sem_preco"])

        # Log per-ativo summary for top ativos
        for ativo in sorted(ativo_counts, key=lambda a: -ativo_counts[a]["dte_range"])[:10]:
            ac = ativo_counts[ativo]
            if ac["dte_range"] > 0:
                logger.debug("CollarCal ativo=%s: dte_range=%d strike_ok=%d ocp_ovd_ok=%d final=%d",
                             ativo, ac["dte_range"], ac["strike_ok"], ac["ocp_ovd_ok"], ac["final"])

        resultados = []

        for ativo in calls_por_ativo:
            if ativo not in puts_por_ativo:
                continue

            calls = calls_por_ativo[ativo]
            puts = puts_por_ativo[ativo]

            preco_ativo = rtd.ler_campo_cache(ativo, "ULT") or 0.0
            if preco_ativo <= 0:
                continue

            calls.sort(key=lambda x: x["strike"])
            puts.sort(key=lambda x: x["strike"])

            pares_testados = 0
            for call in calls:
                sc = call["strike"]
                if sc <= preco_ativo:
                    continue

                for put in puts:
                    sp = put["strike"]
                    if sp >= preco_ativo:
                        continue

                    dte_extra = put["dte"] - call["dte"]
                    if dte_extra < params["dte_extra_min"] or dte_extra > params["dte_extra_max"]:
                        continue

                    pares_testados += 1
                    resultado = calc.calcular(
                        preco_ativo=preco_ativo,
                        strike_call=sc,
                        strike_put=sp,
                        premio_call=call["preco_call"],
                        premio_put=put["preco_put"],
                        cod_call=call["cod_call"],
                        cod_put=put["cod_put"],
                        dte_call=call["dte"],
                        dte_put=put["dte"],
                        ativo=ativo,
                        vencimento_call=call["vencimento"],
                        vencimento_put=put["vencimento"],
                    )

                    if resultado and resultado.viavel:
                        resultados.append(resultado)
                        logger.debug("CollarCal PAR VIÁVEL %s: call=%s(%.0f) put=%s(%.0f) DTE %d+%d pct_cdi=%.2f",
                                     ativo, call["cod_call"], sc, put["cod_put"], sp,
                                     call["dte"], dte_extra, resultado.pct_cdi)

            if pares_testados > 0:
                logger.debug("CollarCal ativo=%s calls=%d puts=%d pares=%d viaveis=%d",
                             ativo, len(calls), len(puts), pares_testados, sum(1 for r in resultados if r.ativo == ativo))

        resultados.sort(key=lambda r: -r.pct_cdi)
        logger.debug("CollarCal TOTAL: %d viaveis em %d ativos", len(resultados), len(set(r.ativo for r in resultados)))
        return resultados
