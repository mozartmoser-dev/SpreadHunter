import logging
from collections import defaultdict
from datetime import date
from typing import Optional

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.calculadora_colar import CalculadoraColar, ResultadoColar, RiscoLeilao, TipoColar
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository, ParametroRepository

logger = logging.getLogger(__name__)


class MonitorColaresUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self._calculadora = None

    def _get_calculadora(self) -> CalculadoraColar:
        if self._calculadora is None:
            param = self.param_repo.get_by_chave("taxa_cdi")
            taxa_cdi = param.valor if param else 0.1450
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

    def varrer(self, rtd=None, dados_mercado: dict | None = None, params: dict | None = None) -> list[ResultadoColar]:
        calc = self._get_calculadora()
        inst_map = self.inst_repo.get_all_mapped()
        self._whitelist_cache = self._get_whitelist()

        if params is None:
            params = {
                "dias_minimos": self._get_param("perf_dias_minimos", 0),
                "dist_max_pct": self._get_param("colar_dist_max_pct", 0.15),
                "qul_min_put": self._get_param("colar_qul_min_put", 100),
                "qul_min_call": self._get_param("colar_qul_min_call", 100),
            }

        hoje = date.today()

        if dados_mercado is not None:
            dados = self._extrair_de_dados_mercado(dados_mercado, inst_map, params, hoje)
        else:
            dados = self._ler_dados_rtd_all(inst_map, rtd, params, hoje)

        return self._combinar_pares(dados, calc, params)

    def _extrair_de_dados_mercado(self, dados_mercado, inst_map, params, hoje):
        grupos = defaultdict(list)
        whitelist = getattr(self, '_whitelist_cache', None)
        for key, dm in dados_mercado.items():
            inst = inst_map.get(key)
            if not inst or not inst.vencimento or inst.vencimento <= hoje:
                continue
            if whitelist is not None and inst.ativo.upper() not in whitelist:
                continue

            preco_ativo = dm.get("preco_ativo", 0.0)
            if not preco_ativo or preco_ativo <= 0:
                continue

            strike = dm.get("strike_rtd", dm.get("strike", 0.0))
            if not strike or strike <= 0:
                continue

            premio_put = dm.get("premio_put", 0.0)
            premio_call = dm.get("premio_call", 0.0)
            if premio_put <= 0 or premio_call <= 0:
                continue

            qul_put = dm.get("qul_put", 0.0) or 0.0
            qul_call = dm.get("qul_call", 0.0) or 0.0
            if qul_put <= 0 or qul_call <= 0:
                continue

            dias_min = params.get("dias_minimos", 0)
            dte = (inst.vencimento - hoje).days
            if dias_min > 0 and dte < dias_min:
                continue

            dados_item = {
                "strike": strike,
                "cod_put": inst.cod_put,
                "cod_call": inst.cod_call,
                "preco_ativo": preco_ativo,
                "preco_compra_ativo": dm.get("of_venda_ativo", 0.0) or 0.0,
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
                continue

            grupo_key = (inst.ativo, inst.vencimento)
            grupos[grupo_key].append(dados_item)

        return grupos

    def _ler_dados_rtd_all(self, inst_map, rtd, params, hoje):
        grupos = defaultdict(list)
        whitelist = getattr(self, '_whitelist_cache', None)

        for key, inst in inst_map.items():
            if not inst.vencimento or inst.vencimento <= hoje:
                continue
            if whitelist is not None and inst.ativo.upper() not in whitelist:
                continue

            dados = self._ler_dados_rtd(inst, rtd)
            if not dados:
                continue

            dias_min = params.get("dias_minimos", 0)
            if dias_min > 0 and dados["dias"] < dias_min:
                continue

            if dados["qul_put"] <= 0 or dados["qul_call"] <= 0:
                continue
            qul_min_put = params.get("qul_min_put", 100)
            qul_min_call = params.get("qul_min_call", 100)
            if dados["qul_put"] < qul_min_put or dados["qul_call"] < qul_min_call:
                continue

            grupo_key = (inst.ativo, inst.vencimento)
            grupos[grupo_key].append(dados)

        return grupos

    def _ler_dados_rtd(self, inst: InstrumentoOpcional, rtd) -> dict | None:
        from src.infrastructure.providers.rtd_config import (
            RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_OFERTA_COMPRA,
            RTD_CAMPO_QTDE_ULT_NEG, RTD_CAMPO_VOL_VENDA, RTD_CAMPO_VOL_COMPRA,
            RTD_CAMPO_STRIKE, RTD_CAMPO_ULTIMO_PRECO,
        )

        preco_ativo = rtd.ler_campo_cache(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
        if not preco_ativo or preco_ativo <= 0:
            return None

        of_venda_ativo = rtd.ler_campo_cache(inst.ativo, RTD_CAMPO_OFERTA_VENDA)

        strike_rtd = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_STRIKE)
        if not strike_rtd or strike_rtd <= 0:
            strike_rtd = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_STRIKE)
        if not strike_rtd or strike_rtd <= 0:
            return None

        of_v_put = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_OFERTA_VENDA) or 0.0
        of_c_call = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_OFERTA_COMPRA) or 0.0
        vov_put = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_VOL_VENDA) or 0.0
        voc_call = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_VOL_COMPRA) or 0.0
        qul_put = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_QTDE_ULT_NEG) or 0.0
        qul_call = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_QTDE_ULT_NEG) or 0.0
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

    def _combinar_pares(self, grupos: dict, calc: CalculadoraColar, params: dict) -> list[ResultadoColar]:
        resultados = []

        for (ativo, vencimento), members in grupos.items():
            if len(members) < 2:
                continue

            members.sort(key=lambda m: m["strike"])
            preco_ativo = members[0]["preco_ativo"]
            dist_max = preco_ativo * params.get("dist_max_pct", 0.15)

            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    put_data = members[i]
                    call_data = members[j]
                    sp = put_data["strike"]
                    sc = call_data["strike"]
                    if sp >= sc:
                        continue
                    if abs(sp - preco_ativo) > dist_max and abs(sc - preco_ativo) > dist_max:
                        continue

                    resultado = calc.calcular(
                        preco_ativo=preco_ativo,
                        strike_put=sp, strike_call=sc,
                        premio_put=put_data["premio_put"],
                        premio_call=call_data["premio_call"],
                        cod_put=put_data["cod_put"],
                        cod_call=call_data["cod_call"],
                        dias=put_data["dias"],
                        vov_put=put_data["vov_put"],
                        voc_call=call_data["voc_call"],
                        status_put=put_data["status_put"],
                        status_call=call_data["status_call"],
                        ativo=ativo, vencimento=vencimento,
                        preco_compra_ativo=put_data.get("preco_compra_ativo"),
                    )
                    if resultado and resultado.viavel:
                        resultados.append(resultado)

        resultados.sort(key=lambda r: -r.pct_cdi)
        return resultados

    def _get_param(self, chave: str, default: float) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()
