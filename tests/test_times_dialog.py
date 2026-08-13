"""Testes do painel Times (times_dialog) — leitura defensiva dos timestamps do DTO."""
from datetime import date, datetime, timezone

from src.application.dtos.dtos import OportunidadeMonitor
from src.domain.services.calculadora_box import ResultadoBox
from src.domain.services.calculadora_colar import ResultadoColar
from src.ui.desktop.times_dialog import _linhas_times, _fmt_ts, _idade


def _linha(linhas, marcador):
    return next(l for l in linhas if l["marcador"] == marcador)


def _r_box():
    return ResultadoBox(
        ativo="PETR4", vencimento=date(2026, 9, 10), strike_k1=18.0, strike_k2=19.0,
        cod_call_k1="PETRH18", cod_put_k1="PETRG18", cod_call_k2="PETRI19",
        cod_put_k2="PETRG19", bid_call_k1=0.1, ask_put_k1=0.1, ask_call_k2=0.1,
        bid_put_k2=0.1, qtd_bid_call_k1=100, qtd_ask_put_k1=100, qtd_ask_call_k2=100,
        qtd_bid_put_k2=100, clr=1.0, distancia=1.0, lucro=0.1, custo_b3=0.01,
        custo_ir=0.0, lucro_liquido=0.09, lucro_pct=0.05, pct_cdi=1.5,
        pct_cdi_liquido=1.4, em_leilao=False, viavel=True, dias=30,
    )


class TestLinhasTimesSemTimestamps:
    def test_todos_marcadores_presentes(self):
        linhas = _linhas_times(_r_box())
        marcadores = [l["marcador"] for l in linhas]
        for m in ["Tn", "T0", "T0b", "T1", "T2", "T3", "T4"]:
            assert m in marcadores, m

    def test_sem_timestamps_hora_fica_dash(self):
        for linha in _linhas_times(_r_box()):
            if linha["marcador"] in ("Tn", "T0", "T0b", "T1", "T2", "T3", "T4"):
                assert linha["hora"] == "-", linha["marcador"]

    def test_onda_default_dash(self):
        assert _linha(_linhas_times(_r_box()), "Onda")["hora"] == "-"

    def test_tn_param_off_mostra_nd_param_off(self):
        linha = _linha(_linhas_times(_r_box(), assinar_timestamp_openfast=False), "Tn")
        assert linha["hora"] == "N/D (param off)"
        assert linha["idade"] == "-"
        assert "param off" in linha["origem"]

    def test_tn_param_unknown_permanece_dash(self):
        for valor in (True, None):
            linha = _linha(_linhas_times(_r_box(), assinar_timestamp_openfast=valor), "Tn")
            assert linha["hora"] == "-", valor

    def test_tn_param_off_com_ts_mostra_hora(self):
        r = _r_box()
        r.ts_origem_ativo = 990.0
        linha = _linha(_linhas_times(r, assinar_timestamp_openfast=False), "Tn")
        assert "N/D" not in linha["hora"]
        assert linha["hora"].startswith("21:16:30")


class TestLinhasTimesComTimestamps:
    def _monitor(self):
        return OportunidadeMonitor(
            instrumento_id=1, ativo="PETR4", strike=18.0,
            vencimento=date(2026, 9, 10), dias=30, cod_put="PETRG180",
            cod_call="PETRH180", tipo_opcao="A",
            ts_ativo_ask=1000.0, ts_origem_ativo=990.0,
            ts_scan=997.0, onda=2,
            detectado_em=datetime(2026, 8, 10, 13, 0, 0, tzinfo=timezone.utc),
        )

    def test_tn_usa_ts_origem_ativo(self):
        linhas = _linhas_times(self._monitor())
        assert _linha(linhas, "Tn")["hora"].startswith("21:16:30")
        assert _linha(linhas, "Tn")["idade"] != "-"

    def test_t0_usa_ts_ativo_ask(self):
        linhas = _linhas_times(self._monitor())
        assert _linha(linhas, "T0")["hora"].startswith("21:16:40")

    def test_onda_preenchida(self):
        assert _linha(_linhas_times(self._monitor()), "Onda")["hora"] == "2"

    def test_ts_scan_entrada_pipeline(self):
        linhas = _linhas_times(self._monitor())
        assert _linha(linhas, "T1")["hora"].startswith("21:16:37")


class TestFormatadores:
    def test_fmt_ts_none(self):
        assert _fmt_ts(None) == "-"

    def test_fmt_ts_valido(self):
        assert _fmt_ts(1000.0).startswith("21:16:40")

    def test_idade_ms(self):
        assert _idade(9999.5, 10000.0) == "500 ms"

    def test_idade_segundos(self):
        assert _idade(9900.0, 9955.0) == "55.0 s"

    def test_idade_minutos(self):
        assert _idade(0.0, 400.5) == "6 min 40 s"

    def test_idade_none(self):
        assert _idade(None, 1000.0) == "-"