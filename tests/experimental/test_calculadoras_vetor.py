import numpy as np
import pytest

from src.domain.services.calculadora_coberta_vetor import calcular_coberta, calcular_comprada
from src.domain.services.calculadora_vendidas_vetor import calcular_vendidas
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3


class TestCalcularVendidas:
    def test_caso_box_sbth_ambos(self):
        res = calcular_vendidas(
            preco_ativo=np.array([18.0, 18.0]),
            of_compra_ativo=np.array([17.9, 17.9]),
            of_compra_put=np.array([0.5, 0.5]),
            of_venda_call=np.array([0.4, 0.4]),
            strike=np.array([18.0, 18.0]),
            dias=np.array([20, 20]),
            vov_put=np.array([1000.0, 1000.0]),
            voc_call=np.array([1000.0, 1000.0]),
            dist_min_ativo=1.20,
            premio_risco=1.10,
            lote_box=100,
            lote_sbth=100,
            taxa_cdi=0.14,
        )
        # recebimento_box = 17.9 + 0.5 - 0.4 = 18.0 > strike? 18.0 > 18.0 = False -> box rejeitado
        assert not res.cond_box.all()
        # cond_sbth: strike > of_compra_ativo * 1.20? 18.0 > 21.48 = False
        assert not res.cond_sbth.all()

    def test_box_valido(self):
        res = calcular_vendidas(
            preco_ativo=np.array([10.0]),
            of_compra_ativo=np.array([9.9]),
            of_compra_put=np.array([1.0]),
            of_venda_call=np.array([0.8]),
            strike=np.array([10.0]),
            dias=np.array([30]),
            vov_put=np.array([1000.0]),
            voc_call=np.array([1000.0]),
            dist_min_ativo=1.20,
            premio_risco=0.0,
            lote_box=100,
            lote_sbth=100,
            taxa_cdi=0.14,
        )
        # recebimento_box = 9.9 + 1.0 - 0.8 = 10.1 > 10 -> True; todas pernas > 0
        assert res.cond_box.all()
        assert not res.cond_sbth.all()  # 10 > 9.9*1.2=11.88 -> False
        assert res.viavel_box.all()

    def test_ir_sobre_ganho_positivo(self):
        custos = CalculadoraCustosB3()
        res = calcular_vendidas(
            preco_ativo=np.array([10.0]),
            of_compra_ativo=np.array([9.9]),
            of_compra_put=np.array([1.0]),
            of_venda_call=np.array([0.8]),
            strike=np.array([10.0]),
            dias=np.array([30]),
            vov_put=np.array([1000.0]),
            voc_call=np.array([1000.0]),
            dist_min_ativo=1.20,
            premio_risco=0.0,
            lote_box=100,
            lote_sbth=100,
            taxa_cdi=0.14,
            custos_b3=custos,
        )
        assert res.cond_box.all()
        assert res.custo_box[0] > 0
        # ganho_antes_ir = receb - strike - custo
        esperado_antes_ir = 10.1 - 10.0 - float(res.custo_box[0])
        np.testing.assert_allclose(res.ganho_antes_ir_box[0], esperado_antes_ir, rtol=1e-12)
        if esperado_antes_ir > 0:
            np.testing.assert_allclose(res.ir_box[0], esperado_antes_ir * custos.taxa_ir, rtol=1e-12)
        else:
            assert res.ir_box[0] == 0.0


class TestCalcularCoberta:
    def test_venda_coberta_valida(self):
        res = calcular_coberta(
            preco_ativo=np.array([20.0]),
            of_compra_ativo=np.array([19.8]),
            of_venda_call=np.array([0.5]),
            voc_call=np.array([500.0]),
            strike=np.array([19.0]),
            dias=np.array([30]),
            premio_risco=0.0,
            lote_call=100,
            taxa_cdi=0.14,
        )
        assert res.cond.all()
        # recebimento = 19.8 - 0.5 = 19.3 > 19 -> True
        assert res.recebimento[0] == pytest.approx(19.3)
        assert res.viavel.all()

    def test_condicao_exige_strike_menor_preco(self):
        res = calcular_coberta(
            preco_ativo=np.array([18.0]),
            of_compra_ativo=np.array([17.9]),
            of_venda_call=np.array([0.5]),
            voc_call=np.array([500.0]),
            strike=np.array([19.0]),
            dias=np.array([30]),
            premio_risco=0.0,
            lote_call=100,
            taxa_cdi=0.14,
        )
        assert not res.cond.all()  # strike 19 < preco 18 = False

    def test_comprada_valida(self):
        res = calcular_comprada(
            preco_ativo=np.array([100.0]),
            of_venda_ativo=np.array([100.2]),
            of_compra_call=np.array([1.5]),
            voc_call=np.array([500.0]),
            strike=np.array([90.0]),
            dias=np.array([10]),
            premio_risco=0.0,
            lote_liquidez=1,
            dist_max_pct=0.80,
            taxa_cdi=0.14,
        )
        # strike_max = 100 * (1 - 0.8) = 20; strike 90 <= 20 = False
        assert not res.cond.all()

    def test_comprada_strike_dentro_do_dist(self):
        res = calcular_comprada(
            preco_ativo=np.array([100.0]),
            of_venda_ativo=np.array([100.2]),
            of_compra_call=np.array([1.5]),
            voc_call=np.array([500.0]),
            strike=np.array([19.0]),
            dias=np.array([10]),
            premio_risco=0.0,
            lote_liquidez=1,
            dist_max_pct=0.80,
            taxa_cdi=0.14,
        )
        # strike_max = 20; 19 <= 20 True; custo_montagem=98.7>0; 19>98.7=False
        assert not res.cond.all()


class TestCustosSemBoca:
    def test_vov_put_zero_nao_quebra(self):
        res = calcular_vendidas(
            preco_ativo=np.array([10.0]),
            of_compra_ativo=np.array([9.9]),
            of_compra_put=np.array([1.0]),
            of_venda_call=np.array([0.8]),
            strike=np.array([10.0]),
            dias=np.array([30]),
            vov_put=np.array([0.0]),
            voc_call=np.array([0.0]),
            dist_min_ativo=1.20,
            premio_risco=1.10,
            lote_box=100,
            lote_sbth=100,
            taxa_cdi=0.14,
        )
        assert res.cond_box.all()
        assert not res.viavel_box.all()  # liquidez zero < lote


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))