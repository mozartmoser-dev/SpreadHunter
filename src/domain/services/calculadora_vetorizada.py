import numpy as np
from datetime import date

from src.domain.services.calendario_b3 import dc_to_du_vetorizado
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3
from dataclasses import dataclass


@dataclass(slots=True)
class ResultadoVetorizado:
    indices_viaveis: np.ndarray
    pct_cdi_box: np.ndarray
    pct_cdi_sbth: np.ndarray
    pct_cdi_box_liquido: np.ndarray
    pct_cdi_sbth_liquido: np.ndarray
    pct_cdi_box_bruto: np.ndarray
    pct_cdi_sbth_bruto: np.ndarray
    pct_ganho_box_bruto: np.ndarray
    pct_ganho_sbth_bruto: np.ndarray
    pct_ganho_box_liquido: np.ndarray
    pct_ganho_sbth_liquido: np.ndarray
    custo_box: np.ndarray
    custo_sbth: np.ndarray
    ganho_box: np.ndarray
    ganho_sbth: np.ndarray
    cdi_periodo: np.ndarray


class CalculadoraVetorizada:
    def __init__(self, taxa_cdi: float, premio_risco_box: float, premio_risco_sbth: float,
                 taxa_emolumento: float | None = None, taxa_liquidacao: float | None = None,
                 taxa_ir: float | None = None):
        self.taxa_cdi = taxa_cdi
        self.premio_risco_box = premio_risco_box
        self.premio_risco_sbth = premio_risco_sbth
        self.custos_b3 = CalculadoraCustosB3(taxa_emolumento, taxa_liquidacao, taxa_ir)

    def calcular(self, 
                 preco_ativo: np.ndarray,
                 of_venda_ativo: np.ndarray,
                 of_venda_put: np.ndarray,
                 of_compra_call: np.ndarray,
                 strike: np.ndarray,
                 dias: np.ndarray,
                 vov_put_boca: np.ndarray,
                 voc_call_boca: np.ndarray,
                 lote_put: float,
                 lote_call: float,
                 em_leilao: np.ndarray,
                 vencimentos: np.ndarray | None = None) -> ResultadoVetorizado:
        
        # 1. Preparação de Dados
        n = len(preco_ativo)
        if n == 0:
            empty = np.array([])
            return ResultadoVetorizado(empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty)

        # Preço de compra do ativo (lógica da calculadora original)
        preco_compra_ativo = np.where(of_venda_ativo > 0, of_venda_ativo, 0.0)
        
        # 2. Cálculos Financeiros
        if vencimentos is not None and len(vencimentos) == n:
            dias_uteis = dc_to_du_vetorizado(date.today(), vencimentos)
        else:
            dias_uteis = np.where(dias > 0, np.round(dias * 252.0 / 365.0).astype(int), 0)
        cdi_periodo = np.where(dias_uteis > 0, (1 + self.taxa_cdi) ** (dias_uteis / 252.0) - 1, 0.0)
        
        custo_b3_sbth = (self.custos_b3.custos_opcao_vetor(of_venda_put, n_pernas=1) +
                         self.custos_b3.custos_stock_vetor(preco_compra_ativo, n_acoes=1))
        premio_medio_box = (of_venda_put + of_compra_call) / 2
        custo_b3_box = (self.custos_b3.custos_opcao_vetor(premio_medio_box, n_pernas=2) +
                        self.custos_b3.custos_stock_vetor(preco_compra_ativo, n_acoes=1))
        
        # SBTH
        custo_sbth = preco_compra_ativo + of_venda_put
        ganho_sbth_bruto = np.where((custo_sbth > 0) & (of_venda_put > 0), strike - custo_sbth, 0.0)
        ganho_sbth = ganho_sbth_bruto - custo_b3_sbth
        pct_ganho_sbth_bruto = np.divide(ganho_sbth_bruto, custo_sbth, out=np.zeros_like(ganho_sbth_bruto), where=custo_sbth > 0)
        pct_ganho_sbth = np.divide(ganho_sbth, custo_sbth, out=np.zeros_like(ganho_sbth), where=custo_sbth > 0)
        pct_cdi_sbth_bruto = np.divide(pct_ganho_sbth_bruto, cdi_periodo, out=np.zeros_like(pct_ganho_sbth_bruto), where=cdi_periodo > 0)
        pct_cdi_sbth = np.divide(pct_ganho_sbth, cdi_periodo, out=np.zeros_like(pct_ganho_sbth), where=cdi_periodo > 0)
        
        # BOX
        custo_box = preco_compra_ativo + of_venda_put - of_compra_call
        ganho_box_bruto = np.where((of_venda_put > 0) & (of_compra_call > 0), strike - custo_box, 0.0)
        ganho_box = ganho_box_bruto - custo_b3_box
        pct_ganho_box_bruto = np.divide(ganho_box_bruto, custo_box, out=np.zeros_like(ganho_box_bruto), where=custo_box > 0)
        pct_ganho_box = np.divide(ganho_box, custo_box, out=np.zeros_like(ganho_box), where=custo_box > 0)
        pct_cdi_box_bruto = np.divide(pct_ganho_box_bruto, cdi_periodo, out=np.zeros_like(pct_ganho_box_bruto), where=cdi_periodo > 0)
        pct_cdi_box = np.divide(pct_ganho_box, cdi_periodo, out=np.zeros_like(pct_ganho_box), where=cdi_periodo > 0)

        # IR
        ir_sbth = self.custos_b3.ajustar_ir_vetor(ganho_sbth)
        ir_box = self.custos_b3.ajustar_ir_vetor(ganho_box)
        ganho_sbth_liq = ganho_sbth - ir_sbth
        ganho_box_liq = ganho_box - ir_box
        pct_ganho_sbth_liq = np.divide(ganho_sbth_liq, custo_sbth, out=np.zeros_like(ganho_sbth_liq), where=custo_sbth > 0)
        pct_ganho_box_liq = np.divide(ganho_box_liq, custo_box, out=np.zeros_like(ganho_box_liq), where=custo_box > 0)
        pct_cdi_sbth_liquido = np.where(cdi_periodo > 0, pct_ganho_sbth_liq / cdi_periodo, 0.0)
        pct_cdi_box_liquido = np.where(cdi_periodo > 0, pct_ganho_box_liq / cdi_periodo, 0.0)
        
        # 3. Verificação de Viabilidade e Classificação
        # Tem liquidez?
        liq_put = vov_put_boca >= lote_put
        liq_call = voc_call_boca >= lote_call
        tem_liquidez = liq_put & liq_call
        
        # É viavel por prêmio de risco? (pré B3, antes IR)
        passa_box = pct_cdi_box_bruto > self.premio_risco_box
        passa_sbth = pct_cdi_sbth_bruto > self.premio_risco_sbth
        
        # Combinado (BOX ou SBTH ou Ambos)
        viavel = (passa_box | passa_sbth) & tem_liquidez  # leilão: identifica visualmente, não descarta
        
        return ResultadoVetorizado(
            indices_viaveis=np.where(viavel)[0],
            pct_cdi_box=pct_cdi_box,
            pct_cdi_sbth=pct_cdi_sbth,
            pct_cdi_box_liquido=pct_cdi_box_liquido,
            pct_cdi_sbth_liquido=pct_cdi_sbth_liquido,
            pct_cdi_box_bruto=pct_cdi_box_bruto,
            pct_cdi_sbth_bruto=pct_cdi_sbth_bruto,
            pct_ganho_box_bruto=pct_ganho_box_bruto,
            pct_ganho_sbth_bruto=pct_ganho_sbth_bruto,
            pct_ganho_box_liquido=pct_ganho_box_liq,
            pct_ganho_sbth_liquido=pct_ganho_sbth_liq,
            custo_box=custo_box,
            custo_sbth=custo_sbth,
            ganho_box=ganho_box,
            ganho_sbth=ganho_sbth,
            cdi_periodo=cdi_periodo
        )
