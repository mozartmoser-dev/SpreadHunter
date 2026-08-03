import logging
import math
import time
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Optional

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.calculadora_colar import CalculadoraColar, ResultadoColar, RiscoLeilao, TipoColar
from src.domain.services.market_data_source import FieldName
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository, ParametroRepository

logger = logging.getLogger(__name__)


# Ordem dos filtros aplicados no varrer(). regras_dialog lê esta lista automaticamente.
FILTROS_COLAR = [
    "1. Vencimento",
    "2. Ativo (whitelist/checklist)",
    "3. Preço do ativo (RTD)",
    "4. Strike (RTD)",
    "5. Prêmios PUT e CALL (RTD)",
    "6. QUL > 0",
    "7. DTE mínimo",
    "8. QUL mínimo",
]


class MonitorColaresUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self._calculadora = None

    def _get_calculadora(self) -> CalculadoraColar:
        if self._calculadora is None:
            param = self.param_repo.get_by_chave("taxa_cdi")
            taxa_cdi = param.valor
            param_risco = self.param_repo.get_by_chave("premio_risco_colar")
            premio = param_risco.valor if param_risco else 0.7
            param_vov = self.param_repo.get_by_chave("colar_risco_baixo_vov_min")
            vov_min = param_vov.valor if param_vov else 1000.0
            emol = self._get_param("taxa_emolumento_pct", 0.00025)
            liq = self._get_param("taxa_liquidacao_pct", 0.000275)
            from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3
            ir = self._get_param("taxa_ir_pct", 0.15)
            custos_b3 = CalculadoraCustosB3(emol, liq, ir)
            self._calculadora = CalculadoraColar(taxa_cdi, premio, colar_risco_baixo_vov_min=vov_min, custos_b3=custos_b3)
        return self._calculadora

    def _get_whitelist(self) -> set[str] | None:
        param = self.param_repo.get_by_chave("white_list_colar")
        if not param or not param.valor:
            return None
        return {a.strip().upper() for a in str(param.valor).split(",") if a.strip()}

    def varrer(self, rtd=None, dados_mercado: dict | None = None, params: dict | None = None, pipeline_tracker: PipelineTracker | None = None) -> list[ResultadoColar]:
        calc = self._get_calculadora()
        inst_map = self.inst_repo.get_all_mapped()
        self._whitelist_cache = self._get_whitelist()

        if params is None:
            params = {
                "dias_minimos": self._get_param("perf_dias_minimos", 0),
                "dist_max_pct": self._get_param("colar_dist_max_pct", 0.15),
                "qul_min_put": self._get_param("colar_qul_min_put", 100),
                "qul_min_call": self._get_param("colar_qul_min_call", 100),
                "qtd_acao": int(self._get_param("colar_qtd_ativo", 100)),
                "qtd_call": int(self._get_param("colar_qtd_call", 100)),
                "qtd_put": int(self._get_param("colar_qtd_put", 100)),
            }

        hoje = date.today()
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

        if dados_mercado is not None:
            dados = self._extrair_de_dados_mercado(dados_mercado, inst_map, params, hoje, pipeline_tracker)
        else:
            dados = self._ler_dados_rtd_all(inst_map, rtd, params, hoje, pipeline_tracker)

        return self._combinar_pares(dados, calc, params, pipeline_tracker, agora)

    def _extrair_de_dados_mercado(self, dados_mercado, inst_map, params, hoje, pipeline_tracker=None):
        grupos = defaultdict(list)
        whitelist = getattr(self, '_whitelist_cache', None)
        c_total = c_venc = c_white = c_preco = c_strike = c_premio = c_qul0 = c_dte = c_qulmin = c_pca_zero = 0
        _t0 = time.perf_counter()
        for key, dm in dados_mercado.items():
            c_total += 1
            ativo_k, cod_put_k = key.split("|", 1)
            inst = inst_map.get((ativo_k, cod_put_k))
            if not inst or not inst.vencimento or inst.vencimento <= hoje:
                c_venc += 1
                continue
            if whitelist is not None and inst.ativo.upper() not in whitelist:
                c_white += 1
                continue

            preco_ativo = dm.get("preco_ativo", 0.0)
            if not preco_ativo or preco_ativo <= 0:
                c_preco += 1
                continue

            strike = dm.get("strike_rtd", dm.get("strike", 0.0))
            if not strike or strike <= 0:
                c_strike += 1
                continue

            premio_put = dm.get("premio_put", 0.0)
            premio_call = dm.get("premio_call", 0.0)
            if premio_put <= 0 or premio_call <= 0:
                c_premio += 1
                continue

            qul_put = dm.get("qul_put", 0.0) or 0.0
            qul_call = dm.get("qul_call", 0.0) or 0.0
            if qul_put <= 0 or qul_call <= 0:
                c_qul0 += 1
                continue

            dias_min = params.get("dias_minimos", 0)
            dte = (inst.vencimento - hoje).days
            if dias_min > 0 and dte < dias_min:
                c_dte += 1
                continue

            of_venda_ativo = dm.get("of_venda_ativo", 0.0) or 0.0
            dados_item = {
                "strike": strike,
                "cod_put": inst.cod_put,
                "cod_call": inst.cod_call,
                "preco_ativo": preco_ativo,
                "preco_compra_ativo": of_venda_ativo if of_venda_ativo > 0 else 0.0,
                "premio_put": premio_put,
                "premio_call": premio_call,
                "vov_put": dm.get("vov_put_boca", 0.0) or 0.0,
                "voc_call": dm.get("voc_call_boca", 0.0) or 0.0,
                "qul_put": qul_put,
                "qul_call": qul_call,
                "status_put": dm.get("status_put", "Aberto"),
                "status_call": dm.get("status_call", "Aberto"),
                "dias": dte,
                "ativo": inst.ativo,
                "vencimento": inst.vencimento,
            }

            qul_min_put = params.get("qul_min_put", 100)
            qul_min_call = params.get("qul_min_call", 100)
            if dados_item["qul_put"] < qul_min_put or dados_item["qul_call"] < qul_min_call:
                c_qulmin += 1
                continue

            if dados_item["preco_compra_ativo"] <= 0:
                c_pca_zero += 1
                continue

            grupo_key = (inst.ativo, inst.vencimento)
            grupos[grupo_key].append(dados_item)

        logger.info("Collar DIAG extrair: total=%d, venc=%d, whitelist=%d, preco_ativo=%d, strike=%d, premio=%d, qul0=%d, dte=%d, qulmin=%d, pca_zero=%d -> grupos=%d",
                     c_total, c_venc, c_white, c_preco, c_strike, c_premio, c_qul0, c_dte, c_qulmin, c_pca_zero, len(grupos))

        if pipeline_tracker is not None:
            pipeline_tracker.nome_estrategia = "COLAR"
            n0 = c_total
            n1 = n0 - c_venc
            n2 = n1 - c_white
            n3 = n2 - c_preco
            n4 = n3 - c_strike
            n5 = n4 - c_premio
            n6 = n5 - c_qul0
            n7 = n6 - c_dte
            n8 = n7 - c_qulmin
            n9 = n8 - c_pca_zero
            tempo_filtro = time.perf_counter() - _t0
            pipeline_tracker.add_stage("1. Vencimento", n0, n1,
                "Opção sem vencimento futuro ou já vencida (vencimento <= hoje)",
                tempo_s=tempo_filtro)
            pipeline_tracker.add_stage("2. Ativo (whitelist)", n1, n2,
                "Ativo não está na whitelist configurada em Parâmetros > COLAR (white_list_colar)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("3. Preço do ativo (RTD)", n2, n3,
                "Preço do ativo zerado no RTD (ULT ou oferta de venda não disponível)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("4. Strike (RTD)", n3, n4,
                "Strike não disponível no RTD (PEX zerado)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("5. Prêmios PUT/CALL (RTD)", n4, n5,
                "Prêmio da PUT ou CALL zerado no RTD — sem oferta de compra/venda",
                tempo_s=0.0)
            pipeline_tracker.add_stage("6. QUL > 0", n5, n6,
                "QUL = 0 em PUT ou CALL — sem negócio no pregão",
                tempo_s=0.0)
            pipeline_tracker.add_stage("7. DTE mínimo", n6, n7,
                f"DTE < {params.get('dias_minimos', 0)}d (Parâmetros > PERFORMANCE > perf_dias_minimos)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("8. QUL mínimo", n7, n8,
                f"QUL abaixo do mínimo: PUT≥{params.get('qul_min_put',100)} CALL≥{params.get('qul_min_call',100)} (Parâmetros > COLAR)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("9. Preço compra ativo", n8, n9,
                "Ask do ativo zerado no RTD — sem oferta de venda disponível",
                tempo_s=0.0)
            logger.info("PipelineTracker (%s): %d -> %d", pipeline_tracker.nome_estrategia, c_total, n9)
            self._ultimo_pipeline = pipeline_tracker

        return grupos

    def _ler_dados_rtd_all(self, inst_map, rtd, params, hoje, pipeline_tracker=None):
        grupos = defaultdict(list)
        whitelist = getattr(self, '_whitelist_cache', None)
        c_total = c_venc = c_white = c_rtd = c_dte = c_qul0 = c_qulmin = c_pca_zero = 0
        _t0 = time.perf_counter()

        for key, inst in inst_map.items():
            c_total += 1
            if not inst.vencimento or inst.vencimento <= hoje:
                c_venc += 1
                continue
            if whitelist is not None and inst.ativo.upper() not in whitelist:
                c_white += 1
                continue

            dados = self._ler_dados_rtd(inst, rtd)
            if not dados:
                c_rtd += 1
                continue

            dias_min = params.get("dias_minimos", 0)
            if dias_min > 0 and dados["dias"] < dias_min:
                c_dte += 1
                continue

            if dados["qul_put"] <= 0 or dados["qul_call"] <= 0:
                c_qul0 += 1
                continue
            qul_min_put = params.get("qul_min_put", 100)
            qul_min_call = params.get("qul_min_call", 100)
            if dados["qul_put"] < qul_min_put or dados["qul_call"] < qul_min_call:
                c_qulmin += 1
                continue

            if dados["preco_compra_ativo"] <= 0:
                c_pca_zero += 1
                continue

            grupo_key = (inst.ativo, inst.vencimento)
            grupos[grupo_key].append(dados)

        if pipeline_tracker is not None:
            n0 = c_total
            n1 = n0 - c_venc
            n2 = n1 - c_white
            n3 = n2 - c_rtd
            n4 = n3 - c_dte
            n5 = n4 - c_qul0
            n6 = n5 - c_qulmin
            n7 = n6 - c_pca_zero
            tempo_rtd = time.perf_counter() - _t0
            pipeline_tracker.add_stage("1. Vencimento", n0, n1,
                "Opção sem vencimento futuro ou já vencida",
                tempo_s=tempo_rtd)
            pipeline_tracker.add_stage("2. Ativo (whitelist/checklist)", n1, n2,
                "Ativo não está na whitelist (Parâmetros > COLAR)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("3. Dados RTD", n2, n3,
                "RTD não retornou dados completos (strike/prêmio/liquidez)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("4. DTE mínimo", n3, n4,
                f"DTE < {params.get('dias_minimos', 0)}d (Parâmetros > PERFORMANCE)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("5. QUL > 0", n4, n5,
                "QUL = 0 em PUT ou CALL — sem negócio no pregão",
                tempo_s=0.0)
            pipeline_tracker.add_stage("6. QUL mínimo", n5, n6,
                f"QUL abaixo do mínimo: PUT≥{params.get('qul_min_put',100)} CALL≥{params.get('qul_min_call',100)} (Parâmetros > COLAR)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("7. Preço compra ativo", n6, n7,
                "Ask do ativo zerado no RTD — sem oferta de venda disponível",
                tempo_s=0.0)

        return grupos

    def _ler_dados_rtd(self, inst: InstrumentoOpcional, rtd) -> dict | None:
        preco_ativo = rtd.ler_campo_cache(inst.ativo, FieldName.ASK)
        if not preco_ativo or preco_ativo <= 0:
            return None

        of_venda_ativo = rtd.ler_campo_cache(inst.ativo, FieldName.ASK)

        # Fontes push (OpenFAST): strike canônico é do banco (opcoes.net.br).
        # "PEX" do servidor pode não ser o strike real para opções.
        if getattr(rtd, 'suporta_push', False):
            strike_rtd = inst.strike
        else:
            strike_rtd = rtd.ler_campo_cache(inst.cod_put, FieldName.STRIKE)
            if not strike_rtd or strike_rtd <= 0:
                strike_rtd = rtd.ler_campo_cache(inst.cod_call, FieldName.STRIKE)
        if not strike_rtd or strike_rtd <= 0:
            return None

        of_v_put = rtd.ler_campo_cache(inst.cod_put, FieldName.ASK) or 0.0
        of_c_call = rtd.ler_campo_cache(inst.cod_call, FieldName.BID) or 0.0
        vov_put = rtd.ler_campo_cache(inst.cod_put, FieldName.VOL_ASK) or 0.0
        voc_call = rtd.ler_campo_cache(inst.cod_call, FieldName.VOL_BID) or 0.0
        qul_put = rtd.ler_campo_cache(inst.cod_put, FieldName.QTD_LAST) or 0.0
        qul_call = rtd.ler_campo_cache(inst.cod_call, FieldName.QTD_LAST) or 0.0
        status_put = rtd.ler_status_cache(inst.cod_put)
        status_call = rtd.ler_status_cache(inst.cod_call)

        return {
            "strike": strike_rtd,
            "cod_put": inst.cod_put,
            "cod_call": inst.cod_call,
            "preco_ativo": preco_ativo,
            "preco_compra_ativo": of_venda_ativo if (of_venda_ativo and of_venda_ativo > 0) else 0.0,
            "premio_put": of_v_put,
            "premio_call": of_c_call,
            "vov_put": vov_put,
            "voc_call": voc_call,
            "qul_put": qul_put,
            "qul_call": qul_call,
            "status_put": status_put,
            "status_call": status_call,
            "dias": inst.dias_ate_vencimento,
            "ativo": inst.ativo,
            "vencimento": inst.vencimento,
        }

    def _combinar_pares(self, grupos: dict, calc: CalculadoraColar, params: dict, pipeline_tracker=None, agora: datetime | None = None) -> list[ResultadoColar]:
        if agora is None:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        resultados = []
        c_grupos = c_poucos = c_pares = c_invalid = c_dist = c_calc_ok = c_calc_none = 0
        total_members = sum(len(m) for m in grupos.values())
        _t0 = time.perf_counter()

        for (ativo, vencimento), members in grupos.items():
            c_grupos += 1
            if len(members) < 2:
                c_poucos += 1
                continue

            members.sort(key=lambda m: m["strike"])
            preco_ativo = members[0]["preco_ativo"]
            dist_max = preco_ativo * params.get("dist_max_pct", 0.15)

            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    c_pares += 1
                    put_data = members[i]
                    call_data = members[j]
                    sp = put_data["strike"]
                    sc = call_data["strike"]
                    if sp >= sc:
                        c_invalid += 1
                        continue
                    if abs(sp - preco_ativo) > dist_max and abs(sc - preco_ativo) > dist_max:
                        c_dist += 1
                        continue

                    resultado = calc.calcular(
                        preco_ativo=preco_ativo,
                        strike_put=sp, strike_call=sc,
                        premio_put=put_data["premio_put"],
                        premio_call=call_data["premio_call"],
                        cod_put=put_data["cod_put"],
                        cod_call=put_data["cod_call"],
                        dias=put_data["dias"],
                        vov_put=put_data["vov_put"],
                        voc_call=put_data["voc_call"],
                        status_put=put_data["status_put"],
                        status_call=put_data["status_call"],
                        ativo=ativo, vencimento=vencimento,
                        preco_compra_ativo=put_data.get("preco_compra_ativo"),
                        qtd_acao=params["qtd_acao"],
                        qtd_call=params["qtd_call"],
                        qtd_put=params["qtd_put"],
                    )
                    if resultado:
                        resultado.detectado_em = agora
                        resultados.append(resultado)
                        c_calc_ok += 1
                    else:
                        c_calc_none += 1

        if pipeline_tracker is not None:
            n_entrada = sum(s.saida for s in pipeline_tracker.stages[-1:]) if pipeline_tracker.stages else total_members
            tempo_pares = time.perf_counter() - _t0
            pipeline_tracker.add_stage("10. Agrupamento (call+put)", total_members, c_grupos,
                "Itens agrupados por ativo+vencimento",
                tempo_s=tempo_pares)
            pipeline_tracker.add_stage("11. Pares válidos", c_pares, c_pares,
                f"{c_invalid} pares com PUT≥CALL, {c_dist} fora da distância máxima",
                tempo_s=0.0)
            pipeline_tracker.add_stage("12. Cálculo de viabilidade", c_pares - c_invalid - c_dist, c_calc_ok,
                f"{c_calc_none} pares inviáveis (prêmio-risco, B3, etc.)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("13. Resultado final", c_calc_ok, sum(1 for r in resultados if r.viavel),
                f"{sum(1 for r in resultados if r.viavel)} viáveis no monitor",
                tempo_s=0.0)
            self._ultimo_pipeline = pipeline_tracker

        logger.info("Collar DIAG pares: grupos=%d, <2membros=%d, pares=%d, sp>=sc=%d, fora_dist=%d, calc_ok=%d, calc_none=%d -> total=%d",
                     c_grupos, c_poucos, c_pares, c_invalid, c_dist, c_calc_ok, c_calc_none, len(resultados))

        if resultados:
            # ── Score de Ranking (Colar Protetivo) ──
            peso_pop = self._get_param("ranking_peso_colar_pop", 3.0)
            peso_cdi = self._get_param("ranking_peso_colar_cdi", 2.0)
            peso_risco = self._get_param("ranking_peso_colar_risco", 1.0)

            def _risco_norm(r):
                return {"Baixo": 1.0, "Médio": 0.5, "Alto": 0.0}.get(r.risco_leilao.value, 0.0)

            def _pop_balance(r):
                pu = r.pop_upside if r.pop_upside is not None else 0
                pd = r.pop_downside if r.pop_downside is not None else 0
                return 100 - abs(pu - pd)

            viaveis = [r for r in resultados if r.viavel]
            raw = []
            for r in viaveis:
                raw.append({
                    "pop": _pop_balance(r),
                    "cdi": r.pct_cdi,
                    "risco": _risco_norm(r),
                })

            if not raw:
                return [r for r in resultados if r.viavel]

            max_pop = max(x["pop"] for x in raw) or 1.0
            max_cdi = max(x["cdi"] for x in raw) or 1.0

            for r, d in zip(viaveis, raw):
                pop_norm = d["pop"] / max_pop
                cdi_norm = d["cdi"] / max_cdi
                risco_norm = d["risco"]
                r.score = round(
                    peso_pop * pop_norm
                    + peso_cdi * cdi_norm
                    + peso_risco * risco_norm,
                    4,
                )

            resultados.sort(key=lambda r: -r.score)
            top5 = [(r.ativo, r.score, r.pct_cdi, r.viavel) for r in resultados[:5]]
            logger.info("Collar DIAG top5 (score): %s", top5)
        resultados = [r for r in resultados if r.viavel]
        return resultados

    def _get_param(self, chave: str, default: float) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()
