import logging
import math
import time
from collections import defaultdict
from datetime import date, datetime

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_put_ratio import (
    CalculadoraPutRatio, ResultadoPutRatio, RATIOS_DEFAULT,
)
from src.domain.services.market_data_source import FieldName
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository, ParametroRepository,
)

logger = logging.getLogger(__name__)


class MonitorPutRatioUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self._calculadora = None

    def _get_calculadora(self) -> CalculadoraPutRatio:
        if self._calculadora is None:
            param_cdi = self.param_repo.get_by_chave("taxa_cdi")
            taxa_cdi = param_cdi.valor if param_cdi else 0.1450
            param_risco = self.param_repo.get_by_chave("put_ratio_premio_risco")
            premio = param_risco.valor if param_risco else 1.0
            emol = self._get_param("taxa_emolumento_pct", 0.00025)
            liq = self._get_param("taxa_liquidacao_pct", 0.000275)
            reg = self._get_param("taxa_registro_pct", 0.0001)
            iss = self._get_param("taxa_iss_pct", 0.0)
            alpha = self._get_param("put_ratio_peso_alpha", 0.5)
            beta = self._get_param("put_ratio_peso_beta", 0.3)
            gamma = self._get_param("put_ratio_peso_gamma", 0.2)
            self._calculadora = CalculadoraPutRatio(taxa_cdi, premio, emol, liq,
                                                     taxa_registro=reg, iss=iss,
                                                     peso_alpha=alpha, peso_beta=beta, peso_gamma=gamma)
        return self._calculadora

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()

    def _get_param(self, chave: str, default: float = 0.0) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def _get_qtd_min_perna(self) -> int:
        param = self.param_repo.get_by_chave("put_ratio_qtd_min")
        return int(param.valor) if param else 100

    def _get_iv_rank_min(self) -> float:
        param = self.param_repo.get_by_chave("put_ratio_iv_rank_min")
        return param.valor if param else 50.0

    def _get_whitelist(self) -> set[str] | None:
        param = self.param_repo.get_by_chave("white_list_put_ratio")
        if param and param.valor:
            raw = str(param.valor)
            ativos = [a.strip().upper() for a in raw.split(",") if a.strip()]
            return set(ativos) if ativos else None
        return None

    def _get_ratios(self) -> list[tuple[int, int]]:
        param = self.param_repo.get_by_chave("put_ratio_ratios")
        if param and param.valor:
            raw = str(param.valor)
            ratios = []
            for part in raw.split(","):
                part = part.strip()
                if "x" in part:
                    try:
                        n1, n2 = part.split("x")
                        ratios.append((int(n1), int(n2)))
                    except ValueError:
                        pass
            return ratios if ratios else RATIOS_DEFAULT
        return RATIOS_DEFAULT

    def _extrair(self, inst: InstrumentoOpcional, rtd, r_cont: float = 0.0) -> dict | None:
        strike = rtd.ler_campo_cache(inst.cod_put, FieldName.STRIKE)
        if not strike or strike <= 0:
            return None

        bid_put = rtd.ler_campo_cache(inst.cod_put, FieldName.BID) or 0.0
        ask_put = rtd.ler_campo_cache(inst.cod_put, FieldName.ASK) or 0.0

        if bid_put <= 0 and ask_put <= 0:
            return None

        preco_ativo = rtd.ler_campo_cache(inst.ativo, FieldName.ASK) or 0.0

        status_put = rtd.ler_status_cache(inst.cod_put)
        status_ativo = rtd.ler_status_cache(inst.ativo)

        # TODO IV Rank/Percentile: bootstrap com get_stock_history_formatted()
        # (opcoesnet_client) → 252d de vol_impl → rank rolante diario
        iv_put = 0.0
        if preco_ativo > 0 and strike > 0 and inst.dias_ate_vencimento > 0:
            mid = ask_put if ask_put > 0 else bid_put
            if mid > 0 and r_cont > 0:
                T = inst.dias_ate_vencimento / 365.0
                iv_put = CalculadoraPutRatio.estimar_iv(mid, preco_ativo, strike, T, r_cont) * 100.0

        return {
            "strike": strike,
            "cod_put": inst.cod_put,
            "bid_put": bid_put,
            "ask_put": ask_put,
            "qtd_bid_put": int(rtd.ler_campo_cache(inst.cod_put, FieldName.VOL_BID) or 0),
            "qtd_ask_put": int(rtd.ler_campo_cache(inst.cod_put, FieldName.VOL_ASK) or 0),
            "em_leilao": not (status_put.lower() == "aberto" and status_ativo.lower() == "aberto"),
            "ativo": inst.ativo,
            "vencimento": inst.vencimento,
            "dias": inst.dias_ate_vencimento,
            "preco_ativo": preco_ativo,
            "iv_put": iv_put,
        }

    def _passa_filtros(self, dados: dict) -> bool:
        if dados["dias"] <= 0:
            return False
        dte_min = self._get_param("put_ratio_dte_min", 20)
        dte_max = self._get_param("put_ratio_dte_max", 60)
        if dados["dias"] < dte_min or dados["dias"] > dte_max:
            return False
        iv_min = self._get_iv_rank_min()
        iv_put = dados.get("iv_put", 0.0)
        if iv_put > 0 and iv_put < iv_min:
            return False
        return True

    def varrer(self, rtd, pipeline_tracker: PipelineTracker | None = None) -> list[ResultadoPutRatio]:
        calc = self._get_calculadora()
        r_cont = math.log(1 + calc.taxa_cdi)
        inst_map = self.inst_repo.get_all_mapped()
        qtd_min = self._get_qtd_min_perna()
        iv_min = self._get_iv_rank_min()
        ratios = self._get_ratios()
        whitelist = self._get_whitelist()

        hoje = date.today()
        agora = datetime.now()
        grupos: dict[tuple[str, date], list[dict]] = defaultdict(list)

        filtro = {"total": 0, "venc": 0, "white": 0, "rtd": 0, "filtros": 0}
        n_passou = 0
        _t0 = time.perf_counter()

        for _key, inst in inst_map.items():
            filtro["total"] += 1
            if not inst.vencimento or inst.vencimento <= hoje:
                filtro["venc"] += 1
                continue
            if whitelist is not None and inst.ativo.upper() not in whitelist:
                filtro["white"] += 1
                continue

            dados = self._extrair(inst, rtd, r_cont)
            if not dados:
                filtro["rtd"] += 1
                continue
            if not self._passa_filtros(dados):
                filtro["filtros"] += 1
                continue

            grupo_key = (inst.ativo, inst.vencimento)
            grupos[grupo_key].append(dados)
            n_passou += 1

        n4 = 0
        if pipeline_tracker is not None:
            pipeline_tracker.nome_estrategia = "PUT_RATIO"
            n0 = filtro["total"]
            n1 = n0 - filtro["venc"]
            n2 = n1 - filtro["white"]
            n3 = n2 - filtro["rtd"]
            n4 = n3 - filtro["filtros"]
            pipeline_tracker.add_stage("1. Vencimento", n0, n1, "Fora do prazo")
            pipeline_tracker.add_stage("2. Ativo (whitelist)", n1, n2, "Fora da whitelist")
            pipeline_tracker.add_stage("3. Dados RTD", n2, n3, "Sem strike")
            pipeline_tracker.add_stage("4. Filtros DTE/IV", n3, n4,
                                       f"DTE [{self._get_param('put_ratio_dte_min', 20)}, {self._get_param('put_ratio_dte_max', 60)}] | IV >= {self._get_iv_rank_min()}%")
            logger.info("PipelineTracker PUT_RATIO: %d -> %d", n0, n_passou)
            self._ultimo_pipeline = pipeline_tracker

        resultados = []

        for (ativo, vencimento), members in grupos.items():
            if len(members) < 2:
                continue

            members.sort(key=lambda m: m["strike"], reverse=True)
            ativo_results = []

            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    k1_data = members[i]
                    k2_data = members[j]

                    iv_put = k1_data["iv_put"]
                    if iv_put > 0 and iv_put < iv_min:
                        continue

                    du = dc_to_du(hoje, vencimento) if vencimento else None

                    for n1, n2 in ratios:
                        resultado = calc.calcular(
                            strike_k1=k1_data["strike"],
                            strike_k2=k2_data["strike"],
                            n1=n1,
                            n2=n2,
                            ask_put_k1=k1_data["ask_put"],
                            bid_put_k2=k2_data["bid_put"],
                            qtd_ask_put_k1=k1_data["qtd_ask_put"],
                            qtd_bid_put_k2=k2_data["qtd_bid_put"],
                            cod_put_k1=k1_data["cod_put"],
                            cod_put_k2=k2_data["cod_put"],
                            ativo=ativo,
                            vencimento=vencimento,
                            dias=k1_data["dias"],
                            em_leilao=k1_data["em_leilao"] or k2_data["em_leilao"],
                            preco_ativo=k1_data.get("preco_ativo", 0.0),
                            qtd_min_perna=qtd_min,
                            du=du,
                        )
                        if resultado:
                            resultado.detectado_em = agora
                            ativo_results.append(resultado)

            ativo_results.sort(key=lambda r: -r.score)
            resultados.extend(ativo_results[:3])

        if pipeline_tracker is not None:
            pipeline_tracker.add_stage("5. Pareamento", n4, len(resultados), "")

        resultados.sort(key=lambda r: -r.score)
        return resultados
