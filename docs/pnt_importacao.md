# Importação de Ordens no PNT (FastTrader)

> Documentação de estudo — 19/06/2026
> Links oficiais consultados:
> - Basket: https://suporte.plugntrade.com.br/hc/pt-br/articles/5022992029979
> - Direcional: https://suporte.plugntrade.com.br/hc/pt-br/articles/5023198795291
> - MultiLeg: https://suporte.plugntrade.com.br/hc/pt-br/articles/5024134177179
> - Spread: https://suporte.plugntrade.com.br/hc/pt-br/articles/5023409776795
> - Gradiente Linear: https://suporte.plugntrade.com.br/hc/pt-br/articles/8859538650523
> - Reinserção: https://suporte.plugntrade.com.br/hc/pt-br/articles/5024652999451
> - Estratégias: https://suporte.plugntrade.com.br/hc/pt-br/articles/9513275849627
> - Canal YouTube: https://www.youtube.com/@plugntrade
> - Vídeo "Rotina otimizada": https://www.youtube.com/watch?v=7N9uxUI4ivA

## Tipos de Importação

| Tipo | ComboBox | Formato | Status |
|------|----------|---------|--------|
| **Direcional** | Robô - Direcional | 3 cols: `Ativo \t C/V \t Qtd` | Dados gerados em `PNTIntegration`, sem automação |
| **MultiLeg** | Robô - MultiLeg (ativo por coluna) | `Ativo1..N \t Lado1..N \t Qtd1..N \t Coeficiente` | ✅ Implementado |
| **Spread** | Robô - Spread | Formato específico (ver abaixo) | ❌ Não implementado |
| **Gradiente Linear** | Boleta própria (não via Ferramentas) | "Importação via edição múltipla" | ❌ Não implementado |

---

## MultiLeg — Nosso Formato Atual (17 colunas)

Gerado por `BoletaDialog._montar_linha()` em `src/ui/desktop/boleta_dialog.py`.

Estratégias: COLAR, COLLAR CALENDARIO, BASKET ITM, BOX 4P, SBTH.

### Para 3 pernas (Collar, Calendar, Basket ITM):

| # | Coluna | Exemplo |
|---|--------|---------|
| 1 | Ativo 1 | PETR4 |
| 2 | Ativo 2 | PETRF173 |
| 3 | Ativo 3 | PETRR173 |
| 4 | Lado 1 | C |
| 5 | Lado 2 | V |
| 6 | Lado 3 | C |
| 7 | Qtd. 1 | 100 |
| 8 | Qtd. 2 | 100 |
| 9 | Qtd. 3 | 100 |
| 10 | Profund. book 1 | 1 |
| 11 | Profund. book 2 | -1 |
| 12 | Profund. book 3 | -1 |
| 13 | Coeficiente (Spread) | 1,23 |
| 14 | Qtd. apregoada 1 | 100 |
| 15 | Qtd. apregoada 2 | 100 |
| 16 | Qtd. apregoada 3 | 100 |
| 17 | Observações | Spreadhunter |

### Para 4 pernas (BOX 4P):

| # | Coluna | Exemplo |
|---|--------|---------|
| 1-4 | Ativo 1..4 | PETRH26, PETRK26, PETRI26, PETRJ26 |
| 5-8 | Lado 1..4 | C, V, V, C |
| 9-12 | Qtd. 1..4 | 1000, 1000, 1000, 1000 |
| 13-16 | Profund. book 1..4 | -1, -1, 1, 1 |
| 17 | Coeficiente (Spread) | -123,45 |
| 18-21 | Qtd. apregoada 1..4 | 100, 100, 100, 100 |
| 22 | Observações | Spreadhunter |

### Linha de exemplo copiável (3 pernas, mensal jun/26):

```
PETR4	PETRF173	PETRR173	C	V	C	100	100	100	1	-1	-1	1,23	100	100	100	Spreadhunter
```

---

## MultiLeg — Formato Oficial PNT (10 colunas para 3 pernas)

Fonte: https://suporte.plugntrade.com.br/hc/pt-br/articles/5024134177179

```
Ativo1 | Ativo2 | Ativo3 | Lado1 | Lado2 | Lado3 | Qtd1 | Qtd2 | Qtd3 | Coeficiente
```

A documentação oficial NÃO inclui Profundidade, Qtd Apregoada nem Observações no formato MultiLeg. O PNT permite colunas extras se marcadas na seção "Colunas" do dialog de importação.

### Diferenças entre nosso formato e o oficial:

| Colunas | Oficial (10) | Nosso (17) |
|---------|-------------|-------------|
| Ativo | 3 | 3 |
| Lado | 3 | 3 |
| Qtd | 3 | 3 |
| Profund. book | — | 3 (extra) |
| Coeficiente | 1 | 1 |
| Qtd. apregoada | — | 3 (extra) |
| Observações | — | 1 (extra) |

**Problema potencial**: O PNT pode "se perder" se o dialog de importação não tiver as colunas extras configuradas nos checkboxes. É necessário verificar se as colunas de Profundidade, Qtd Apreg e Observações estão marcadas na interface de importação.

---

## Spread — (A implementar)

Fonte: https://suporte.plugntrade.com.br/hc/pt-br/articles/5023409776795

A documentação é basicamente imagens. O fluxo de navegação no PNT:
- Robô → Comprar → Spread → Spread – Diferença ($)

O formato do Spread é diferente do MultiLeg — usa uma estrutura mais próxima do Direcional.
Pendente de investigação detalhada.

---

## Direcional — Formato (sem automação)

Fonte: https://suporte.plugntrade.com.br/hc/pt-br/articles/5023198795291

```
Ativo \t C/V \t Qtd
PETR4   C   100
PETRH26 C   100
```

Código em `PNTIntegration._preparar_dados_clipboard()` em `src/infrastructure/integrations/pnt.py`.
Usado para BOX e SBTH (atualmente só copia pro clipboard, sem navegação automática).

---

## Automação — `executar_automacao_pnt()`

Arquivo: `src/infrastructure/integrations/pnt.py`

Fluxo:
1. Localiza PNT (processo `PnT.Inteface.exe` > título)
2. Minimiza IDE (VS Code, Cursor, etc.)
3. Força foco no PNT (SwitchToThisWindow + truque Alt key)
4. `Alt+F` → abre Ferramentas
5. `↓4 + Enter` → Importação de Basket/Ordens
6. Localiza ComboBox via Win32 (`_achar_combobox`)
7. Seleciona "Robô - MultiLeg (ativo por coluna)" via `CB_FINDSTRINGEXACT` + clique + teclado
8. `Tab + Ctrl+V` → cola o basket

A automação atual só cobre MultiLeg. Para Spread e Direcional seria necessário:
- Navegação diferente no menu (ou fluxo diferente)
- Seleção de item diferente no ComboBox

---

## Arquivos Relacionados

| Arquivo | Propósito |
|---------|-----------|
| `src/infrastructure/integrations/pnt.py` | Automação PNT + PNTIntegration |
| `src/ui/desktop/boleta_dialog.py` | Dialog da boleta MultiLeg |
| `src/ui/desktop/pnt_utils.py` | Utilitários (copiar basket, fmt_br) |
| `test_pnt_automacao.py` | Teste manual da automação |
| `tests/infrastructure/test_pnt.py` | Testes unitários |
| `scratch/test_click.py` | Testes de clique no menu |
| `scratch/pnt_screens/` | Screenshots de debug |

---

## Exemplo MultiLeg com Opções Mensais PETR4

Séries mensais disponíveis no banco (19/06/2026):

| Vencimento | PUT | CALL |
|------------|-----|------|
| 19/06/2026 | PETRR173 | PETRF173 |
| 17/07/2026 | PETRS748 | PETRG748 |
| 21/08/2026 | PETRT694 | PETRH694 |
| 18/09/2026 | PETRU966 | PETRI966 |
| 16/10/2026 | PETRV253 | PETRJ253 |
| 19/11/2026 | PETRW131 | PETRK131 |
