import logging
import time
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_box import CalculadoraBox, ResultadoBox
from src.domain.services.market_data_source import FieldName
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository, ParametroRepository, TaxaAluguelRepository
from src.infrastructure.providers import stale_trace


class MonitorBoxUseCase:
    def __init__(self, db_path=None, mpp_use_case=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self._calculadora = None
        self._mpp_use_case = mpp_use_case

    def _get_calculadora(self) -> CalculadoraBox:
        if self._calculadora is None:
            param_cdi = self.param_repo.get_by_chave("taxa_cdi")
            taxa_cdi = param_cdi.valor
            param_risco = self.param_repo.get_by_chave("box_premio_risco")
            premio = param_risco.valor if param_risco else 1.08
            emol = self._get_param("taxa_emolumento_pct", 0.00025)
            liq = self._get_param("taxa_liquidacao_pct", 0.000275)
            reg = self._get_param("taxa_registro_pct", 0.0001)
            iss = self._get_param("taxa_iss_pct", 0.0)
            self._calculadora = CalculadoraBox(taxa_cdi, premio, emol, liq, taxa_registro=reg, iss=iss)
        return self._calculadora

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()

    def _get_param(self, chave: str, default: float = 0.0) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def _get_qtd_min_perna(self) -> int:
        param = self.param_repo.get_by_chave("box_qtd_min")
        return int(param.valor) if param else 100

    def _soh_europeia(self) -> bool:
        param = self.param_repo.get_by_chave("box_soh_europeia")
        return bool(param.valor) if param else True

    def _get_whitelist(self) -> set[str] | None:
        param = self.param_repo.get_by_chave("white_list_box4p")
        if param and param.valor:
            raw = str(param.valor)
            ativos = [a.strip().upper() for a in raw.split(",") if a.strip()]
            return set(ativos) if ativos else None
        return None

    def _extrair(self, inst: InstrumentoOpcional, rtd) -> dict | None:
        c_put = rtd.ler_campos(inst.cod_put, FieldName.STRIKE, FieldName.BID, FieldName.ASK, FieldName.VOL_BID, FieldName.VOL_ASK)
        c_call = rtd.ler_campos(inst.cod_call, FieldName.STRIKE, FieldName.BID, FieldName.ASK, FieldName.VOL_BID, FieldName.VOL_ASK)
        stale_trace.log_consumo("BOX4P", {inst.cod_put.upper(), inst.cod_call.upper()}, rtd)

        strike = c_put.get(FieldName.STRIKE)
        if not strike or strike <= 0:
            strike = c_call.get(FieldName.STRIKE)
        if not strike or strike <= 0:
            return None

        status_put = rtd.ler_status_cache(inst.cod_put)
        status_call = rtd.ler_status_cache(inst.cod_call)
        status_ativo = rtd.ler_status_cache(inst.ativo)

        return {
            "strike": strike,
            "cod_put": inst.cod_put,
            "cod_call": inst.cod_call,
            "bid_call": c_call.get(FieldName.BID) or 0.0,
            "ask_call": c_call.get(FieldName.ASK) or 0.0,
            "bid_put": c_put.get(FieldName.BID) or 0.0,
            "ask_put": c_put.get(FieldName.ASK) or 0.0,
            "qtd_bid_call": int(c_call.get(FieldName.VOL_BID) or 0),
            "qtd_ask_call": int(c_call.get(FieldName.VOL_ASK) or 0),
            "qtd_bid_put": int(c_put.get(FieldName.VOL_BID) or 0),
            "qtd_ask_put": int(c_put.get(FieldName.VOL_ASK) or 0),
            "em_leilao": not (
                status_put.lower() == "aberto"
                and status_call.lower() == "aberto"
                and status_ativo.lower() == "aberto"
            ),
            "ativo": inst.ativo,
            "vencimento": inst.vencimento,
            "dias": inst.dias_ate_vencimento,
            "tipo_opcao": inst.tipo_opcao,
        }

    def _passa_filtros(self, dados: dict) -> bool:
        if dados["dias"] <= 0:
            return False
        dias_min = self._get_param("perf_dias_minimos", 10)
        if dados["dias"] < dias_min:
            return False
        return True

    def varrer(self, rtd, pipeline_tracker: PipelineTracker | None = None) -> list[ResultadoBox]:
        calc = self._get_calculadora()
        inst_map = self.inst_repo.get_all_mapped()
        qtd_min = self._get_qtd_min_perna()
        soh_europeia = self._soh_europeia()
        spread_max_pct = self._get_param("box_spread_max_pct", 0.40)
        whitelist = self._get_whitelist()
        taxa_repo = TaxaAluguelRepository(self.db_path)
        taxa_map = taxa_repo.get_latest_all()

        hoje = date.today()
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        grupos: dict[tuple[str, date], list[dict]] = defaultdict(list)

        filtro = {"total": 0, "venc": 0, "white": 0, "rtd": 0, "filtros": 0, "grupos": 0}
        n_passou = 0
        _t0 = time.perf_counter()

        for key, inst in inst_map.items():
            filtro["total"] += 1
            if not inst.vencimento or inst.vencimento <= hoje:
                filtro["venc"] += 1
                continue
            if whitelist is not None and inst.ativo.upper() not in whitelist:
                filtro["white"] += 1
                continue

            dados = self._extrair(inst, rtd)
            if not dados:
                filtro["rtd"] += 1
                continue
            if not self._passa_filtros(dados):
                filtro["filtros"] += 1
                continue

            grupo_key = (inst.ativo, inst.vencimento)
            grupos[grupo_key].append(dados)
            n_passou += 1

        if pipeline_tracker is not None:
            pipeline_tracker.nome_estrategia = "BOX_4P"
            n0 = filtro["total"]
            n1 = n0 - filtro["venc"]
            n2 = n1 - filtro["white"]
            n3 = n2 - filtro["rtd"]
            n4 = n3 - filtro["filtros"]
            tempo_filtro = time.perf_counter() - _t0
            pipeline_tracker.add_stage("1. Vencimento", n0, n1,
                "Opção sem vencimento futuro ou já vencida",
                tempo_s=tempo_filtro)
            pipeline_tracker.add_stage("2. Ativo (whitelist)", n1, n2,
                "Ativo não está na whitelist (Parâmetros > BOX_4P > white_list_box4p)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("3. Dados RTD", n2, n3,
                "RTD não retornou strike (PEX) para PUT ou CALL",
                tempo_s=0.0)
            pipeline_tracker.add_stage("4. Filtros (DTE)", n3, n4,
                f"DTE < {self._get_param('perf_dias_minimos', 10)}d ou dias <= 0",
                tempo_s=0.0)
            pipeline_tracker.add_stage("5. Pareamento", n4, n_passou,
                "Agrupados por ativo+vencimento para formar pares de strike. "
                "Se box_soh_europeia=True, a CALL vendida (K1) deve ser Europeia",
                tempo_s=0.0)
            logger.info("PipelineTracker BOX_4P: %d -> %d", n0, n_passou)
            self._ultimo_pipeline = pipeline_tracker

        resultados = []

        for (ativo, vencimento), members in grupos.items():
            if len(members) < 2:
                continue

            spot = rtd.ler_campo_cache(ativo, FieldName.ASK) or 0.0
            stale_trace.log_consumo("BOX4P", {ativo.upper()}, rtd)
            spread_limite = spot * spread_max_pct if spot > 0 and spread_max_pct > 0 else float("inf")

            members.sort(key=lambda m: m["strike"])

            du = dc_to_du(hoje, vencimento) if vencimento else None

            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    k1_data = members[i]
                    k2_data = members[j]

                    if (k2_data["strike"] - k1_data["strike"]) > spread_limite:
                        break

                    if soh_europeia and k1_data["tipo_opcao"] != TipoOpcao.EUROPEIA:
                        continue

                    resultado = calc.calcular(
                        strike_k1=k1_data["strike"],
                        strike_k2=k2_data["strike"],
                        bid_call_k1=k1_data["bid_call"],
                        ask_put_k1=k1_data["ask_put"],
                        ask_call_k2=k2_data["ask_call"],
                        bid_put_k2=k2_data["bid_put"],
                        qtd_bid_call_k1=k1_data["qtd_bid_call"],
                        qtd_ask_put_k1=k1_data["qtd_ask_put"],
                        qtd_ask_call_k2=k2_data["qtd_ask_call"],
                        qtd_bid_put_k2=k2_data["qtd_bid_put"],
                        cod_call_k1=k1_data["cod_call"],
                        cod_put_k1=k1_data["cod_put"],
                        cod_call_k2=k2_data["cod_call"],
                        cod_put_k2=k2_data["cod_put"],
                        ativo=ativo,
                        vencimento=vencimento,
                        dias=k1_data["dias"],
                        em_leilao=k1_data["em_leilao"] or k2_data["em_leilao"],
                        qtd_min_perna=qtd_min,
                        tipo_opcao=k1_data["tipo_opcao"].value,
                        du=du,
                    )

                    if resultado:
                        taxa_ent = taxa_map.get(ativo)
                        resultado.taxa_aluguel = taxa_ent.taxa_atual if taxa_ent else 0.0
                        resultado.detectado_em = agora
                        resultados.append(resultado)
                        if resultado.viavel and self._mpp_use_case:
                            self._mpp_use_case.registrar_box_encontrado(
                                ativo, k1_data["strike"], k2_data["strike"],
                                resultado.pct_cdi, encontrado=True
                            )

                    resultado_long = calc.calcular_long(
                        strike_k1=k1_data["strike"],
                        strike_k2=k2_data["strike"],
                        ask_call_k1=k1_data["ask_call"],
                        bid_put_k1=k1_data["bid_put"],
                        bid_call_k2=k2_data["bid_call"],
                        ask_put_k2=k2_data["ask_put"],
                        qtd_ask_call_k1=k1_data["qtd_ask_call"],
                        qtd_bid_put_k1=k1_data["qtd_bid_put"],
                        qtd_bid_call_k2=k2_data["qtd_bid_call"],
                        qtd_ask_put_k2=k2_data["qtd_ask_put"],
                        cod_call_k1=k1_data["cod_call"],
                        cod_put_k1=k1_data["cod_put"],
                        cod_call_k2=k2_data["cod_call"],
                        cod_put_k2=k2_data["cod_put"],
                        ativo=ativo,
                        vencimento=vencimento,
                        dias=k1_data["dias"],
                        em_leilao=k1_data["em_leilao"] or k2_data["em_leilao"],
                        qtd_min_perna=qtd_min,
                        tipo_opcao=k2_data["tipo_opcao"].value,
                        du=du,
                    )
                    if resultado_long:
                        taxa_ent = taxa_map.get(ativo)
                        resultado_long.taxa_aluguel = taxa_ent.taxa_atual if taxa_ent else 0.0
                        resultado_long.detectado_em = agora
                        resultados.append(resultado_long)
                        if resultado_long.viavel and self._mpp_use_case:
                            self._mpp_use_case.registrar_box_encontrado(
                                ativo, k1_data["strike"], k2_data["strike"],
                                resultado_long.pct_cdi, encontrado=True
                            )

        resultados.sort(key=lambda r: -r.lucro_pct)
        return resultados

    def confirmar_resultados(self, rtd, resultados):
        if not hasattr(rtd, 'forcar_leitura'):
            return resultados
        calc = self._get_calculadora()
        qtd_min = self._get_qtd_min_perna()
        hoje = date.today()
        confirmados = []
        for r in resultados:
            if not r.viavel:
                confirmados.append(r)
                continue
            bid_c1 = rtd.forcar_leitura(r.cod_call_k1, FieldName.BID)
            ask_p1 = rtd.forcar_leitura(r.cod_put_k1, FieldName.ASK)
            ask_c2 = rtd.forcar_leitura(r.cod_call_k2, FieldName.ASK)
            bid_p2 = rtd.forcar_leitura(r.cod_put_k2, FieldName.BID)
            if any(v is None or v <= 0 for v in (bid_c1, ask_p1, ask_c2, bid_p2)):
                continue
            du = dc_to_du(hoje, r.vencimento) if r.vencimento else None
            novo = calc.calcular(
                strike_k1=r.strike_k1, strike_k2=r.strike_k2,
                bid_call_k1=bid_c1, ask_put_k1=ask_p1,
                ask_call_k2=ask_c2, bid_put_k2=bid_p2,
                qtd_bid_call_k1=r.qtd_bid_call_k1, qtd_ask_put_k1=r.qtd_ask_put_k1,
                qtd_ask_call_k2=r.qtd_ask_call_k2, qtd_bid_put_k2=r.qtd_bid_put_k2,
                cod_call_k1=r.cod_call_k1, cod_put_k1=r.cod_put_k1,
                cod_call_k2=r.cod_call_k2, cod_put_k2=r.cod_put_k2,
                ativo=r.ativo, vencimento=r.vencimento, dias=r.dias,
                em_leilao=r.em_leilao, qtd_min_perna=qtd_min,
                tipo_opcao=r.tipo_opcao, du=du,
            )
            if novo and novo.viavel:
                novo.taxa_aluguel = r.taxa_aluguel
                novo.detectado_em = r.detectado_em
                confirmados.append(novo)
        return confirmados
