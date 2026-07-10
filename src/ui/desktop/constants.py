"""Constantes compartilhadas entre dialogs/desktop da UI.

Centraliza sentinelas e strings magicas para reduzir acoplamento implicito
entre modulos (ex.: "TODOS" usado em listas de ativos).
"""

#: Sentinel usado em QListWidgetItens para o item "selecionar todos".
SELETOR_TODOS = "TODOS"
