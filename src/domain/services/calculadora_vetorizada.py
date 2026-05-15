import numpy as np
from dataclasses import dataclass

@dataclass
class ResultadoVetorizado:
    indices_viaveis: np.ndarray
    pct_cdi_box: np.ndarray
    pct_cdi_sbth: np.ndarray
    custo_box: np.ndarray
    custo_sbth: np.ndarray
    ganho_box: np.ndarray
    ganho_sbth: np.ndarray
    cdi_periodo: np.ndarray

class CalculadoraVetorizada:
    def __init__(self, taxa_cdi: float, premio_risco_box: float, premio_risco_sbth: float):
        self.taxa_cdi = taxa_cdi
        self.premio_risco_box = premio_risco_box
        self.premio_risco_sbth = premio_risco_sbth

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
                 em_leilao: np.ndarray) -> ResultadoVetorizado:
        
        # 1. Preparação de Dados
        n = len(preco_ativo)
        if n == 0:
            empty = np.array([])
            return ResultadoVetorizado(empty, empty, empty, empty, empty, empty, empty, empty)

        # Preço de compra do ativo (lógica da calculadora original)
        preco_compra_ativo = np.where(of_venda_ativo > 0, of_venda_ativo, preco_ativo + 0.01)
        
        # 2. Cálculos Financeiros
        cdi_periodo = np.where(dias > 0, (1 + self.taxa_cdi) ** (dias / 365.0) - 1, 0.0)
        
        # SBTH
        custo_sbth = preco_compra_ativo + of_venda_put
        ganho_sbth = np.where((custo_sbth > 0) & (of_venda_put > 0), (strike - custo_sbth) / custo_sbth, 0.0)
        pct_cdi_sbth = np.where(cdi_periodo > 0, ganho_sbth / cdi_periodo, 0.0)
        
        # BOX
        custo_box = preco_compra_ativo + of_venda_put - of_compra_call
        ganho_box = np.where((custo_box > 0) & (of_venda_put > 0) & (of_compra_call > 0), (strike - custo_box) / custo_box, 0.0)
        pct_cdi_box = np.where(cdi_periodo > 0, ganho_box / cdi_periodo, 0.0)
        
        # 3. Verificação de Viabilidade e Classificação
        # Tem liquidez?
        liq_put = vov_put_boca >= lote_put
        liq_call = voc_call_boca >= lote_call
        tem_liquidez = liq_put & liq_call
        
        # É viavel por prêmio de risco?
        passa_box = pct_cdi_box > self.premio_risco_box
        passa_sbth = pct_cdi_sbth > self.premio_risco_sbth
        
        # Combinado (BOX ou SBTH ou Ambos)
        viavel = (passa_box | passa_sbth) & tem_liquidez & (~em_leilao)
        
        return ResultadoVetorizado(
            indices_viaveis=np.where(viavel)[0],
            pct_cdi_box=pct_cdi_box,
            pct_cdi_sbth=pct_cdi_sbth,
            custo_box=custo_box,
            custo_sbth=custo_sbth,
            ganho_box=ganho_box,
            ganho_sbth=ganho_sbth,
            cdi_periodo=cdi_periodo
        )
