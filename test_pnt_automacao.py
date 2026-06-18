"""Teste da automação PNT com dados mockados (mercado fechado)."""
import pyperclip

# Dados mockados no formato MultiLeg (ativo por coluna) — 17 colunas
# ativos(3) + lados(3) + qtds(3) + profs(3) + coeficiente(1) + qtd_apreg(3) + obs(1)
MOCK_BASKET = (
    "PETR4\tPETRH25\tPETRI25\t"
    "C\tC\tV\t"
    "100\t100\t100\t"
    "1\t1\t1\t"
    "1,23\t"
    "100\t100\t100\t"
    "Spreadhunter"
)

pyperclip.copy(MOCK_BASKET)
print("[OK] Dados mockados copiados para o clipboard")

from src.infrastructure.integrations.pnt import executar_automacao_pnt
resultado = executar_automacao_pnt()
print(f"\nResultado: {'Sucesso' if resultado else 'Falha'}")
