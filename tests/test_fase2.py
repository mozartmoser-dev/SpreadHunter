import tempfile
from datetime import date, timedelta
from pathlib import Path

from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
from src.infrastructure.importers.excel_importer import extrair_strike, parse_vencimento
from src.domain.services.calculadora_box_sbth import CalculadoraBoxSbth, DadosMercado
from src.domain.services.elegibilidade_pescaria import ElegibilidadePescaria, CandidatoPescaria
from src.domain.services.montadora_box_itm import MontadoraBoxItm
from src.domain.rules.classificacao_oportunidade import ClassificacaoOportunidade
from src.domain.entities.oportunidade import Oportunidade, ClassificacaoOp
from src.domain.services.calculadora_box_sbth import ResultadoBOXSBTH

import pytest


class TestExtrairStrike:
    def test_strike_3_digitos(self):
        assert extrair_strike("A1MDQ124") == 12.4

    def test_strike_2_digitos(self):
        assert extrair_strike("BOVAT88") == 88.0

    def test_strike_1_digito(self):
        assert extrair_strike("BOVAH2") == 2.0

    def test_strike_vazio(self):
        assert extrair_strike("") is None

    def test_strike_sem_numeros(self):
        assert extrair_strike("ABCDEF") is None

    def test_strike_4_digitos(self):
        assert extrair_strike("BOVAH9950") == 995.0


class TestParseVencimento:
    def test_formato_brasileiro(self):
        result = parse_vencimento("15/01/2027")
        assert result == date(2027, 1, 15)

    def test_formato_iso(self):
        result = parse_vencimento("2027-01-15")
        assert result == date(2027, 1, 15)

    def test_datetime(self):
        from datetime import datetime
        result = parse_vencimento(datetime(2027, 1, 15))
        assert result == date(2027, 1, 15)

    def test_none(self):
        assert parse_vencimento(None) is None


class TestCalculadoraBoxSbth:
    @pytest.fixture
    def calc(self):
        return CalculadoraBoxSbth(taxa_cdi=0.1450, premio_risco_box=1.5, premio_risco_sbth=1.2)

    def test_cdi_periodo(self, calc):
        cdi = calc.calcular_cdi_periodo(252)
        assert abs(cdi - 0.1450) < 0.001

    def test_cdi_periodo_zero_dias(self, calc):
        assert calc.calcular_cdi_periodo(0) == 0.0

    def test_cdi_periodo_14_dias_uteis(self, calc):
        cdi = calc.calcular_cdi_periodo(14)
        assert cdi > 0
        assert cdi < 0.1450

    def test_calcular_box_classificacao(self, calc):
        dados = DadosMercado(
            preco_ativo=35.0, of_compra_ativo=34.9, of_venda_ativo=35.1,
            of_compra_put=2.0, of_venda_put=2.1,
            of_compra_call=2.5, of_venda_call=2.6,
            strike=40.0, premio_put=2.0, premio_call=2.5, dias=20
        )
        result = calc.calcular(dados)
        assert result.classificacao in ("1BOX", "2SBTH", "3BOXSBTH", "TP.Op")
        assert result.cdi_periodo > 0
        assert result.custo_sbth > 0
        assert result.custo_box > 0

    def test_custo_sbth_com_of_venda_ativo(self, calc):
        dados = DadosMercado(
            preco_ativo=35.0, of_compra_ativo=34.9, of_venda_ativo=35.1,
            of_compra_put=2.0, of_venda_put=2.5,
            of_compra_call=2.0, of_venda_call=2.6,
            strike=40.0, premio_put=2.5, premio_call=2.0, dias=20
        )
        result = calc.calcular(dados)
        assert result.custo_sbth == 37.6  # of_venda_ativo(35.1) + of_venda_put(2.5)

    def test_custo_sbth_sem_ask_ativo_retorna_zero(self, calc):
        dados = DadosMercado(
            preco_ativo=35.0, of_compra_ativo=0, of_venda_ativo=0,
            of_compra_put=2.0, of_venda_put=2.5,
            of_compra_call=2.0, of_venda_call=2.6,
            strike=40.0, premio_put=2.5, premio_call=2.0, dias=20
        )
        result = calc.calcular(dados)
        assert result.custo_sbth == 0.0  # sem ASK do ativo, inviável

    def test_custo_box_com_of_venda_ativo(self, calc):
        dados = DadosMercado(
            preco_ativo=35.0, of_compra_ativo=34.9, of_venda_ativo=35.1,
            of_compra_put=2.0, of_venda_put=2.5,
            of_compra_call=2.0, of_venda_call=2.6,
            strike=40.0, premio_put=2.5, premio_call=2.0, dias=20
        )
        result = calc.calcular(dados)
        assert result.custo_box == 35.6  # of_venda_ativo(35.1) + of_venda_put(2.5) - of_compra_call(2.0)

    def test_pct_ganho_e_cdi(self, calc):
        dados = DadosMercado(
            preco_ativo=35.0, of_compra_ativo=34.9, of_venda_ativo=35.1,
            of_compra_put=1.0, of_venda_put=1.5,
            of_compra_call=3.0, of_venda_call=3.5,
            strike=40.0, premio_put=1.5, premio_call=3.0, dias=60
        )
        result = calc.calcular(dados)
        assert result.pct_ganho_box > 0
        assert result.pct_cdi_box > 0
        assert result.pct_ganho_sbth > 0
        assert result.pct_cdi_sbth > 0

    def test_custo_zero_se_of_venda_put_zero(self, calc):
        dados = DadosMercado(
            preco_ativo=35.0, of_compra_ativo=34.9, of_venda_ativo=35.1,
            of_compra_put=2.0, of_venda_put=0,
            of_compra_call=2.5, of_venda_call=2.6,
            strike=40.0, premio_put=0, premio_call=2.5, dias=20
        )
        result = calc.calcular(dados)
        assert result.custo_sbth == 0
        assert result.custo_box == 0


class TestElegibilidadePescaria:
    @pytest.fixture
    def eleg(self):
        return ElegibilidadePescaria(taxa_ganho=10.0)

    def test_candidato_elegivel(self, eleg):
        candidato = CandidatoPescaria(
            instrumento_id=1, ativo="BOVA11", vencimento="2026-08-21",
            strike_call_itm=10.0, cod_call_itm="BOVAH100",
            of_venda_call=0.5, preco_ativo=18.0, col31_valor=9.0
        )
        resultado = eleg.filtrar_candidatos(
            [candidato], "BOVA11", "2026-08-21", strike_atm=18.0
        )
        assert len(resultado) == 1

    def test_candidato_ativo_diferente(self, eleg):
        candidato = CandidatoPescaria(
            instrumento_id=1, ativo="PETR4", vencimento="2026-08-21",
            strike_call_itm=10.0, cod_call_itm="PETRH100",
            of_venda_call=0.5, preco_ativo=18.0, col31_valor=9.0
        )
        resultado = eleg.filtrar_candidatos(
            [candidato], "BOVA11", "2026-08-21", strike_atm=18.0
        )
        assert len(resultado) == 0

    def test_candidato_strike_nao_itm(self, eleg):
        candidato = CandidatoPescaria(
            instrumento_id=1, ativo="BOVA11", vencimento="2026-08-21",
            strike_call_itm=15.0, cod_call_itm="BOVAH150",
            of_venda_call=0.5, preco_ativo=18.0, col31_valor=9.0
        )
        resultado = eleg.filtrar_candidatos(
            [candidato], "BOVA11", "2026-08-21", strike_atm=18.0
        )
        assert len(resultado) == 0

    def test_candidato_sem_oferta_venda(self, eleg):
        candidato = CandidatoPescaria(
            instrumento_id=1, ativo="BOVA11", vencimento="2026-08-21",
            strike_call_itm=10.0, cod_call_itm="BOVAH100",
            of_venda_call=0.0, preco_ativo=18.0, col31_valor=9.0
        )
        resultado = eleg.filtrar_candidatos(
            [candidato], "BOVA11", "2026-08-21", strike_atm=18.0
        )
        assert len(resultado) == 0

    def test_calcular_valor_limite(self, eleg):
        limite = eleg.calcular_valor_limite(strike_atm=18.0, strike_itm=10.0)
        assert limite == 8.0 * 0.9  # spread=8, (100-10)/100 = 0.9
        assert abs(limite - 7.2) < 0.001


class TestMontadoraBoxItm:
    @pytest.fixture
    def montadora(self):
        return MontadoraBoxItm(profundidade_call_itm=-1)

    def test_montar_3_pernas(self, montadora):
        basket = montadora.montar_3_pernas(
            cod_call_itm="BOVAH100", cod_put_atm="BOVAT180",
            cod_call_atm="BOVAH180", estrutura_id=1,
            coefic_alvo=1.0, coefic_mercado=0.9, taxa_ganho=10.0
        )
        assert basket.tipo.value == "BOX_ITM_BASKET"
        assert len(basket.pernas) == 3
        assert basket.pernas[0].codigo == "BOVAH100"
        assert basket.pernas[0].lado.value == "C"
        assert basket.pernas[1].codigo == "BOVAT180"
        assert basket.pernas[1].lado.value == "C"
        assert basket.pernas[2].codigo == "BOVAH180"
        assert basket.pernas[2].lado.value == "V"
        assert basket.pernas[0].profundidade == -1
        assert basket.pernas[1].profundidade == 0

    def test_calcular_coeficientes(self, montadora):
        alvo, mercado = montadora.calcular_coeficientes(
            strike_atm=18.0, strike_itm=10.0,
            premio_call_atm=2.5, premio_call_itm=8.0, premio_put_atm=2.0
        )
        assert alvo == 1.0
        assert mercado == 0.9375  # (8+2-2.5)/8 = 7.5/8


class TestClassificacaoOportunidade:
    def test_classificar_box(self):
        resultado = ResultadoBOXSBTH(
            custo_sbth=100, pct_ganho_sbth=0.10, pct_cdi_sbth=2.0,
            custo_box=100, pct_ganho_box=0.80, pct_cdi_box=3.0,
            cdi_periodo=0.01, classificacao="1BOX", operacao="BOX"
        )
        assert ClassificacaoOportunidade.classificar(resultado) == ClassificacaoOp.BOX_1

    def test_classificar_sbth(self):
        resultado = ResultadoBOXSBTH(
            custo_sbth=100, pct_ganho_sbth=0.50, pct_cdi_sbth=2.5,
            custo_box=100, pct_ganho_box=0.10, pct_cdi_box=0.5,
            cdi_periodo=0.01, classificacao="2SBTH", operacao="SBTH"
        )
        assert ClassificacaoOportunidade.classificar(resultado) == ClassificacaoOp.SBTH_2

    def test_filtrar_viaveis(self):
        ops = [
            Oportunidade(
                instrumento_id=1, preco_ativo=38.0, strike=38.0, dias=20,
                cdi_periodo=0.01, custo_sbth=100, pct_ganho_sbth=0.15,
                pct_cdi_sbth=1.5,
                custo_box=100, pct_ganho_box=0.20, pct_cdi_box=2.0,
                classificacao=ClassificacaoOp.BOX_1, operacao="BOX"
            ),
            Oportunidade(
                instrumento_id=2, preco_ativo=38.0, strike=38.0, dias=20,
                cdi_periodo=0.01, custo_sbth=100, pct_ganho_sbth=0.0,
                pct_cdi_sbth=0.0,
                custo_box=100, pct_ganho_box=0.0, pct_cdi_box=0.0,
                classificacao=ClassificacaoOp.TP_OP, operacao="NEUTRA"
            ),
        ]
        viaveis = ClassificacaoOportunidade.filtrar_viaveis(ops)
        assert len(viaveis) == 1
        assert viaveis[0].operacao == "BOX"

    def test_filtrar_sem_leilao(self):
        ops = [
            Oportunidade(
                instrumento_id=1, preco_ativo=38.0, strike=38.0, dias=20,
                cdi_periodo=0.01, custo_sbth=100, pct_ganho_sbth=0.15,
                pct_cdi_sbth=1.5,
                custo_box=100, pct_ganho_box=0.20, pct_cdi_box=2.0,
                classificacao=ClassificacaoOp.BOX_1, operacao="BOX",
                snapshot_mercado={"em_leilao": False}
            ),
            Oportunidade(
                instrumento_id=2, preco_ativo=38.0, strike=38.0, dias=20,
                cdi_periodo=0.01, custo_sbth=100, pct_ganho_sbth=0.0,
                pct_cdi_sbth=0.0,
                custo_box=100, pct_ganho_box=0.0, pct_cdi_box=0.0,
                classificacao=ClassificacaoOp.TP_OP, operacao="NEUTRA",
                snapshot_mercado={"em_leilao": True}
            ),
        ]
        filtradas = ClassificacaoOportunidade.filtrar_sem_leilao(ops)
        assert len(filtradas) == 1
