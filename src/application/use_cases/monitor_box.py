from collections import defaultdict
from datetime import date

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.calculadora_box import CalculadoraBox, ResultadoBox
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository, ParametroRepository


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
            taxa_cdi = param_cdi.valor if param_cdi else 0.1450
            param_risco = self.param_repo.get_by_chave("box_premio_risco")
            premio = param_risco.valor if param_risco else 1.08
            emol = self._get_param("taxa_emolumento_pct", 0.00025)
            liq = self._get_param("taxa_liquidacao_pct", 0.000275)
            self._calculadora = CalculadoraBox(taxa_cdi, premio, emol, liq)
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
        strike = rtd.ler_campo_cache(inst.cod_put, "PEX")
        if not strike or strike <= 0:
            strike = rtd.ler_campo_cache(inst.cod_call, "PEX")
        if not strike or strike <= 0:
            return None

        status_put = rtd.ler_status_cache(inst.cod_put)
        status_call = rtd.ler_status_cache(inst.cod_call)
        status_ativo = rtd.ler_status_cache(inst.ativo)

        return {
            "strike": strike,
            "cod_put": inst.cod_put,
            "cod_call": inst.cod_call,
            "bid_call": rtd.ler_campo_cache(inst.cod_call, "OCP") or 0.0,
            "ask_call": rtd.ler_campo_cache(inst.cod_call, "OVD") or 0.0,
            "bid_put": rtd.ler_campo_cache(inst.cod_put, "OCP") or 0.0,
            "ask_put": rtd.ler_campo_cache(inst.cod_put, "OVD") or 0.0,
            "qtd_bid_call": int(rtd.ler_campo_cache(inst.cod_call, "VOC") or 0),
            "qtd_ask_call": int(rtd.ler_campo_cache(inst.cod_call, "VOV") or 0),
            "qtd_bid_put": int(rtd.ler_campo_cache(inst.cod_put, "VOC") or 0),
            "qtd_ask_put": int(rtd.ler_campo_cache(inst.cod_put, "VOV") or 0),
            "em_leilao": not (
                status_put.lower() == "aberto"
                and status_call.lower() == "aberto"
                and status_ativo.lower() == "aberto"
            ),
            "ativo": inst.ativo,
            "vencimento": inst.vencimento,
            "dias": inst.dias_ate_vencimento,
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
        whitelist = self._get_whitelist()

        hoje = date.today()
        grupos: dict[tuple[str, date], list[dict]] = defaultdict(list)

        filtro = {"total": 0, "venc": 0, "tipo": 0, "white": 0, "rtd": 0, "filtros": 0, "grupos": 0}
        n_passou = 0

        for key, inst in inst_map.items():
            filtro["total"] += 1
            if not inst.vencimento or inst.vencimento <= hoje:
                filtro["venc"] += 1
                continue
            if soh_europeia and inst.tipo_opcao != TipoOpcao.EUROPEIA:
                filtro["tipo"] += 1
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
            n2 = n1 - filtro["tipo"]
            n3 = n2 - filtro["white"]
            n4 = n3 - filtro["rtd"]
            n5 = n4 - filtro["filtros"]
            pipeline_tracker.add_stage("1. Vencimento", n0, n1,
                "Opção sem vencimento futuro ou já vencida")
            pipeline_tracker.add_stage("2. Tipo (Europeia)", n1, n2,
                "Só aceita opções Europeias (Parâmetros > BOX_4P > box_soh_europeia)")
            pipeline_tracker.add_stage("3. Ativo (whitelist)", n2, n3,
                "Ativo não está na whitelist (Parâmetros > BOX_4P > white_list_box4p)")
            pipeline_tracker.add_stage("4. Dados RTD", n3, n4,
                "RTD não retornou strike (PEX) para PUT ou CALL")
            pipeline_tracker.add_stage("5. Filtros (DTE/leilão)", n4, n5,
                f"DTE < {self._get_param('perf_dias_minimos', 10)}d ou dias <= 0")
            pipeline_tracker.add_stage("6. Pareamento", n5, n_passou,
                "Agrupados por ativo+vencimento para formar pares de strike")
            logger.info("PipelineTracker BOX_4P: %d -> %d", n0, n_passou)
            self._ultimo_pipeline = pipeline_tracker

        resultados = []

        for (ativo, vencimento), members in grupos.items():
            if len(members) < 2:
                continue

            members.sort(key=lambda m: m["strike"])

            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    k1_data = members[i]
                    k2_data = members[j]

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
                    )

                    if resultado:
                        resultados.append(resultado)
                        if resultado.viavel and self._mpp_use_case:
                            self._mpp_use_case.registrar_box_encontrado(
                                ativo, k1_data["strike"], k2_data["strike"],
                                resultado.pct_cdi, encontrado=True
                            )

        resultados.sort(key=lambda r: -r.lucro_pct)
        return resultados
