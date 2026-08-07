# constants (UI Desktop)

Sentinelas compartilhadas entre diálogos da UI Desktop. Centraliza strings mágicas para reduzir acoplamento implícito entre módulos.

## Contrato (Requisitos)

### `SELETOR_TODOS`
**Garante:**
1. Valor constante `"TODOS"` usado como sentinel em `QListWidgetItem` para o item "selecionar todos" em listas de ativos.

## Dependências Diretas (por import)

Nenhuma — módulo puramente declarativo, sem imports.

## Métricas

| Linhas | 8 |
| Testes | Não |

## Notas

- **Data da criação:** 2026-07-09
- Único arquivo de "constantes" da UI. Conforme o sistema crescer, espera-se que mais sentinelas migrem para cá.
- Atualmente apenas 1 sentinel definido. O comentário no docstring sugere que foi criado como ponto de partida para centralização futura.
