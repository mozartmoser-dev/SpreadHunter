# flag_icons

Geração de ícones de bandeira para a coluna `tipo_opcao` (MOD) nas tabelas de monitoramento. Renderiza bandeiras via `QPainter` (sem dependências externas de imagem): bandeira dos EUA para CALLs Americanas (tipo A) e bandeira da União Europeia (12 estrelas em anel) para CALLs Europeias (tipo E) e todas as PUTs (que são sempre Europeias na B3).

Mantém cache em memória (`_CACHE: dict[str, QIcon]`) para evitar re-renderização.

## Contrato (Requisitos)

### `flag_icon(tipo_opcao) -> QIcon`
**Garante:**
1. Se `tipo_opcao` está em `_CACHE`, retorna ícone cached.
2. Para `"A"`: renderiza bandeira dos EUA (13 faixas + cantão azul com estrelas).
3. Para qualquer outro valor: renderiza bandeira da UE (fundo azul + 12 estrelas amarelas em anel).
4. Armazena no cache antes de retornar.

### `_pixmap_us(size=18) -> QPixmap`
**Garante:**
1. Gera bandeira dos EUA de `size×size` pixels com cantos arredondados (r=2).
2. 13 faixas alternadas vermelhas (#B22234) e brancas (#FFFFFF).
3. Cantão azul (#3C3B6E) no topo esquerdo (40% largura, 54% altura).
4. 30 estrelas brancas (5 linhas × 6 colunas) no cantão.

### `_pixmap_eu(size=18) -> QPixmap`
**Garante:**
1. Gera bandeira da UE de `size×size` pixels com cantos arredondados.
2. Fundo azul (#003399).
3. 12 estrelas amarelas (#FFCC00) em anel (raio 34% do size, estrelas com raio 6% do size).

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `math` | — | Cálculo de posições das estrelas no anel |
| `PySide6.QtCore` | `Qt`, `QPointF` | Transparência e posicionamento |
| `PySide6.QtGui` | `QColor`, `QIcon`, `QPainter`, `QPainterPath`, `QPixmap`, `QPolygonF`, `QPen` | Renderização das bandeiras |

## Métricas

| Linhas | 82 |
| Testes | Não |

## Notas

- **Data da criação:** 2026-07-13
- A bandeira dos EUA tem 30 estrelas (5×6) em vez das 50 oficiais. Isso é uma simplificação visual — as estrelas são pequenas demais (size=18) para 50 serem distinguíveis.
- A função `_hex` converte strings hex para `QColor` — usada apenas internamente.
- `_clip_rounded` aplica clip path com cantos arredondados ao painter — todas as bandeiras têm bordas arredondadas.
- A convenção de PUTs como Europeias segue a regra #2 do AGENTS.md: "MOD (`tipo_opcao`) só da CALL. PUTs B3 são Europeias (`E`)".
- O cache é um dict simples no nível do módulo — não tem TTL ou limite de tamanho. Como só existem 2 valores possíveis (A/E), isso nunca será problema.
