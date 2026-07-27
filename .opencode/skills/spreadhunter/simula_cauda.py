"""Simulação: para cada alvo (2.5/3.0/3.5/4.0), quantos pct_cdi_base gerariam
variante de cauda, e qual ratio seria necessário."""
import sys
from src.domain.services.calculadora_cauda_assincrona import CalculadoraCaudaAssincrona

base = dict(
    preco_ativo=25.0,
    strike_call=20.0,
    strike_put=23.0,
    premio_call=5.40,
    premio_put=0.10,
    dte_call=35,
    ativo="PETR4",
    iv_call_pct=100.0,
    pnl_projetado_base=0.30,
    capital_empregado_base=19.70,
    taxa_cdi=0.145,
    calda_desvios_cauda=3.0,
    calda_ratio_max=50,
    custo_b3_base=0.0,
    preco_compra=24.50,
)

def count_viaveis(calda_premio_risco, pct_cdi_lista):
    v = []
    nao_viavel_com_gap_negativo = 0
    sem_ratio_valido = 0
    for pct in pct_cdi_lista:
        # gap = target - pnl_base; com pnl_base fixo, gap maior quando alvo maior.
        # pct_cdi_base � s� informativo, n�o entra no c�lculo de gap diretamente.
        result = CalculadoraCaudaAssincrona.calcular(
            **base,
            pct_cdi_base=pct,
            pnl_projetado_base=base["pnl_projetado_base"],
            capital_empregado_base=base["capital_empregado_base"],
            calda_premio_risco=calda_premio_risco,
        )
        if result is None:
            # pode ser gap <= 0 ou sem ratio v�lido
            # calcula gap para distinguir
            from src.domain.services.calendario_b3 import dc_to_du
            du_total = dc_to_du(None, None, 35)
            cdi_periodo = (1 + 0.145) * (du_total / 252.0) - 1
            target_pnl = 19.70 * cdi_periodo * calda_premio_risco
            gap = target_pnl - 0.30
            if gap <= 0:
                nao_viavel_com_gap_negativo += 1
            else:
                sem_ratio_valido += 1
            continue
        v.append((pct, result.ratio_call, result.pnl_com_ratio, result.breakeven_superior, result.breakeven_ok))
    return v, nao_viavel_com_gap_negativo, sem_ratio_valido

pct_cdi_lista = [1.8, 2.0, 2.2, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]

print("Comparação: alvos calda_premio_risco x pct_cdi_base\n" + "=" * 100)
for alvo in [2.2, 2.5, 3.0, 3.5, 4.0]:
    viaveis, gap_neg, sem_ratio = count_viaveis(alvo, pct_cdi_lista)
    print(f"\n>>> calda_premio_risco = {alvo}")
    print(f"  Disparos com sucesso: {len(viaveis)}/{len(pct_cdi_lista)}")
    print(f"  gap<=0 (par j� bate alvo): {gap_neg}")
    print(f"  gap>0 mas sem ratio v�lido no filtro 3s: {sem_ratio}")
    if viaveis:
        print(f"  Detalhes:")
        for pct, ratio, pnl, be, be_ok in viaveis:
            print(f"    pct_cdi_base={pct:.1f}x  ratio={ratio:3d}  pnl_ratio={pnl:.4f}  be={be}  ok={be_ok}")
