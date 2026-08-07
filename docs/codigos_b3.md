# Códigos B3 — Opções sobre Ações

## Estrutura do código

```
T T T T L S S S [W n]
│ │ │ │ │ │ │ │   │ │
│ │ │ │ │ │ │ │   │ └─ Número da semana (1-5)
│ │ │ │ │ │ │ │   └─── W = série semanal
│ │ │ │ │ │ └─┴─────── Dígitos do strike (preço × 100, sem vírgula)
│ │ │ │ └───────────── Letra da série (mês CALL, mês PUT, ou W para semanal)
│ └─┴───────────────── Prefixo do ativo (4 letras)
```

**Posições (0-indexed):**
- `0-3`: Ticker do ativo (ex: `PETR`)
- `4`: Letra da série
- `5+`: Dígitos do strike
- **Semanal**: `W` na posição `-2` (penúltimo) + dígito da semana em `-1`

## Códigos de mês (posição 4)

| Mês | CALL | PUT |
|-----|------|-----|
| Jan | A | M |
| Fev | B | N |
| Mar | C | O |
| Abr | D | P |
| Mai | E | Q |
| Jun | F | R |
| Jul | G | S |
| Ago | H | T |
| Set | I | U |
| Out | J | V |
| Nov | K | **W** |
| Dez | L | X |

## Mensal vs. Semanal

| | Mensal | Semanal |
|---|---|---|
| Letra da série | Posição 4 (A-L CALL, M-X PUT) | Posição -2 (`W`) |
| Sufixo | Nenhum | `W1` a `W5` (posições -2 e -1) |
| Exemplo CALL | `PETRA265` (Jan, strike 2.65) | `PETRQ555W5` (semana 5, strike 5.55) |
| Exemplo PUT | `PETRM265` (Jan, strike 2.65) | `PETRQ555W5` (semana 5, strike 5.55) |

**Atenção:** PUT de Novembro usa `W` na **posição 4** (ex: `PETRW265`). Não confundir com semanal (`W` na posição **-2**). O check correto para semanal é `cod[-2] == 'W'`.

## Detecção de semanal

```python
def _is_weekly(cod: str) -> bool:
    return len(cod) >= 2 and cod[-2].upper() == "W"
```

Regex equivalente (menos precisa): `W([1-9])` — usada em `grade_opcoes_dialog.py:_WEEK_RE`.

## Implementações no código

| Local | Uso |
|---|---|
| `main_window.py:_is_weekly()` | Prefixo "S-" nos labels de vencimento |
| `grade_opcoes_dialog.py:_WEEK_RE` | Classificação da série na grade de opções |
| `importflash.py` | Importação via API `OptionsChain` (W1-W4 no campo de série) |
