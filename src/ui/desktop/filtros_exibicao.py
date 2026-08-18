"""Filtros de apresentação do checkbox "Exibir Todas" (Monitor Principal).

Puramente de exibição: não recalcula, não consulta mercado/banco — apenas
filtra a lista de resultados já calculados e cacheados pela UI.

"Exibir Todas" mostra oportunidades não-viáveis (que não atingem todos os
critérios de rentabilidade/viabilidade), preservando a lógica de cálculo.
Não tem efeito sobre classificações "TP.Op" — estas nunca são materializadas.
"""


def _filtra_exibir_todas_viavel(resultados, mostrar_todas):
    """Vendidas/Coberta: com 'Exibir Todas' desmarcado, oculta não-viáveis."""
    if mostrar_todas:
        return resultados
    return [r for r in resultados if getattr(r, 'viavel', False)]
