from datetime import date

import pytest

from src.application.use_cases.monitor_put_ratio import (
    MonitorPutRatioUseCase,
    _is_weekly,
)
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao


class _FakeParam:
    def __init__(self, valor):
        self.valor = valor


class _FakeParamRepo:
    def __init__(self, valores):
        self._valores = dict(valores)

    def get_by_chave(self, chave):
        v = self._valores.get(chave)
        return _FakeParam(v) if v is not None else None

    def invalidate_cache(self):
        pass


class _FakeInstRepo:
    def __init__(self, insts):
        self._insts = insts

    def get_all_mapped(self):
        return {f"{i.ativo}|{i.cod_put}": i for i in self._insts}


def _inst(ativo, cod, vencimento):
    return InstrumentoOpcional(
        ativo=ativo,
        cod_put=cod,
        cod_call=cod,
        vencimento=vencimento,
        tipo_opcao=TipoOpcao.EUROPEIA,
        strike=28.0,
    )


def _uc(insts, filtro_semanal, monkeypatch):
    params = {
        "taxa_cdi": 0.145,
        "put_ratio_premio_risco": 1.0,
        "put_ratio_iv_rank_min": 0.0,
        "perf_filtro_semanal": float(filtro_semanal),
    }
    uc = MonitorPutRatioUseCase(db_path=None)
    uc.inst_repo = _FakeInstRepo(insts)
    uc.param_repo = _FakeParamRepo(params)

    calls = []

    def recorder(inst, rtd, r_cont=0.0):
        calls.append(inst.cod_put)
        return {
            "strike": 28.0,
            "cod_put": inst.cod_put,
            "bid_put": 1.0,
            "ask_put": 1.1,
            "qtd_bid_put": 500,
            "qtd_ask_put": 500,
            "em_leilao": False,
            "ativo": inst.ativo,
            "vencimento": inst.vencimento,
            "dias": 45,
            "preco_ativo": 30.0,
            "iv_put": 0.0,
        }

    uc._extrair = recorder
    return uc, calls


class TestIsWeekly:
    def test_semanal_detectada(self):
        assert _is_weekly("PETRH30W1") is True

    def test_mensal_nao_detectada(self):
        assert _is_weekly("PETRH30") is False

    def test_put_novembro_pos4_nao_confundido(self):
        assert _is_weekly("PETRW265") is False

    def test_none_e_codigo_curto(self):
        assert _is_weekly(None) is False
        assert _is_weekly("P1") is False


class TestFiltroSemanalNoVarrer:
    def test_exclui_semanais_quando_ativado(self, monkeypatch):
        venc = date(2026, 12, 18)
        insts = [
            _inst("PETR4", "PETRH30", venc),
            _inst("PETR4", "PETRH30W1", venc),
        ]
        uc, calls = _uc(insts, filtro_semanal=1, monkeypatch=monkeypatch)
        uc.varrer(rtd=None)
        assert "PETRH30W1" not in calls
        assert "PETRH30" in calls

    def test_inclui_semanais_quando_desativado(self, monkeypatch):
        venc = date(2026, 12, 18)
        insts = [
            _inst("PETR4", "PETRH30", venc),
            _inst("PETR4", "PETRH30W1", venc),
        ]
        uc, calls = _uc(insts, filtro_semanal=0, monkeypatch=monkeypatch)
        uc.varrer(rtd=None)
        assert "PETRH30W1" in calls
        assert "PETRH30" in calls