from datetime import date

from src.ui.desktop.mercado_topbar import (
    _contrato_bimestral_ativo, _segunda_quarta, _cod_fut,
)


class TestSegundaQuarta:
    def test_ago_2026_segunda_quarta_dia12(self):
        assert _segunda_quarta(2026, 8) == date(2026, 8, 12)

    def test_out_2026_segunda_quarta_dia14(self):
        assert _segunda_quarta(2026, 10) == date(2026, 10, 14)

    def test_fev_2026_segunda_quarta_dia11(self):
        assert _segunda_quarta(2026, 2) == date(2026, 2, 11)


class TestContratoBimestralAtivo:
    def test_antes_do_vencimento_retorna_mes_corrente(self):
        assert _contrato_bimestral_ativo(date(2026, 8, 11)) == (2026, 8)

    def test_no_dia_do_vencimento_ainda_e_front(self):
        assert _contrato_bimestral_ativo(date(2026, 8, 12)) == (2026, 8)

    def test_no_dia_seguinte_ao_vencimento_roda_para_out(self):
        assert _contrato_bimestral_ativo(date(2026, 8, 13)) == (2026, 10)

    def test_hoje_14ago2026_passado_vencimento_retorna_out(self):
        assert _contrato_bimestral_ativo(date(2026, 8, 14)) == (2026, 10)

    def test_janeiro_antes_de_fev_retorna_fev(self):
        assert _contrato_bimestral_ativo(date(2026, 1, 5)) == (2026, 2)

    def test_dezembro_apos_vencimento_vai_para_fev_proximo_ano(self):
        assert _contrato_bimestral_ativo(date(2026, 12, 31)) == (2027, 2)

    def test_win_apos_vencimento_de_agosto_assina_out(self):
        a, m = _contrato_bimestral_ativo(date(2026, 8, 14))
        assert _cod_fut("WIN", a, m) == "winv26"
        assert _cod_fut("WDO", a, m) == "wdov26"