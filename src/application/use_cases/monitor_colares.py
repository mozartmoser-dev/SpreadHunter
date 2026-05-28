from collections import defaultdict
from datetime import date
from typing import Optional

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.calculadora_colar import CalculadoraColar, ResultadoColar, RiscoLeilao, TipoColar
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository, ParametroRepository


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
            premio = param_risco.valor if param_risco else 1.0
            self._calculadora = CalculadoraColar(taxa_cdi, premio)
        return self._calculadora

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()

    def _ler_dados(self, inst: InstrumentoOpcional, rtd) -> dict | None:
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
        status_put = rtd.ler_status_cache(inst.cod_put) or "Aberto"
        status_call = rtd.ler_status_cache(inst.cod_call) or "Aberto"

        return {
            "strike": strike_rtd,
            "cod_put": inst.cod_put,
            "cod_call": inst.cod_call,
            "preco_ativo": preco_ativo,
            "preco_compra_ativo": of_venda_ativo if (of_venda_ativo and of_venda_ativo > 0) else preco_ativo,
            "premio_put": of_v_put,
            "premio_call": of_c_call,
            "vov_put": vov_put,
            "voc_call": voc_call,
            "qul_put": qul_put,
            "qul_call": qul_call,
            "status_put": status_put,
            "status_call": status_call,
            "ativo": inst.ativo,
            "vencimento": inst.vencimento,
            "dias": inst.dias_ate_vencimento,
        }

    def _passa_filtros(self, dados: dict, params: dict) -> bool:
        dias = dados["dias"]
        if dias <= 0:
            return False
        dias_min = params.get("dias_minimos", 0)
        if dias_min > 0 and dias < dias_min:
            return False
        if dados["qul_put"] <= 0 or dados["qul_call"] <= 0:
            return False
        return True

    def varrer(self, rtd, params: dict | None = None) -> list[ResultadoColar]:
        calc = self._get_calculadora()
        inst_map = self.inst_repo.get_all_mapped()

        if params is None:
            params = {
                "dias_minimos": self._get_param("perf_dias_minimos", 0),
                "dist_max_pct": self._get_param("colar_dist_max_pct", 0.3),
            }

        hoje = date.today()
        grupos: dict[tuple[str, date], list[dict]] = defaultdict(list)

        for key, inst in inst_map.items():
            if not inst.vencimento or inst.vencimento <= hoje:
                continue

            dados = self._ler_dados(inst, rtd)
            if not dados:
                continue
            if not self._passa_filtros(dados, params):
                continue

            grupo_key = (inst.ativo, inst.vencimento)
            grupos[grupo_key].append(dados)

        resultados = []

        for (ativo, vencimento), members in grupos.items():
            if len(members) < 2:
                continue

            members.sort(key=lambda m: m["strike"])
            preco_ativo = members[0]["preco_ativo"]
            dist_max = preco_ativo * params.get("dist_max_pct", 0.3)

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
                        strike_put=sp,
                        strike_call=sc,
                        premio_put=put_data["premio_put"],
                        premio_call=call_data["premio_call"],
                        cod_put=put_data["cod_put"],
                        cod_call=call_data["cod_call"],
                        dias=put_data["dias"],
                        vov_put=put_data["vov_put"],
                        voc_call=call_data["voc_call"],
                        status_put=put_data["status_put"],
                        status_call=call_data["status_call"],
                        ativo=ativo,
                        vencimento=vencimento,
                        preco_compra_ativo=put_data.get("preco_compra_ativo"),
                    )

                    if resultado and resultado.viavel:
                        resultados.append(resultado)

        resultados.sort(key=lambda r: -r.pct_cdi)
        return resultados

    def _get_param(self, chave: str, default: float) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default
