# CalculadorasDialog

## Propósito

Diálogo unificado com abas de calculadoras financeiras: Black-Scholes (preço, IV, gregas, sensibilidade ±2σ) e CDI (valor a investir para receber strike no vencimento). Ambas as abas leem `taxa_cdi` do banco. A aba Black-Scholes inclui captura OCR via Tesseract (seleção de área na tela para ler código de opção direto do Profit Pro). Substitui os antigos diálogos separados `calculadora_dialog.py` e `calculadora_cdi_dialog.py`.

## Contrato (Requisitos)

### Black-Scholes (`BlackScholesWidget`)
**Garante:**
1. Inputs: Ativo, Strike, Preço Atual, Prêmio, DTE, Taxa CDI, Taxa Juros, Tipo (Call/Put), Estilo (Europeia/Americana), Cálculo (Preço Justo/Volatilidade Implícita).
2. Preço justo: calcula via `CalculadoraColar.calcular_preco_justo_bs()`.
3. IV (Volatilidade Implícita): calcula via Newton-Raphson com tolerância configurável.
4. Gregas: Delta, Gamma, Theta, Vega, Rho — exibidas com sinal e formatação apropriada.
5. Sensibilidade ±2σ: tabela com preço do ativo variando em passos de 0.5σ, mostrando preço da opção, PnL e variação %.
6. DTE calculado a partir da data de vencimento (usa `dc_to_du` para dias úteis) ou campo direto.

### CDI (`CdiWidget`)
**Garante:**
1. Input: Strike desejado, Data de vencimento, Taxa CDI anual.
2. Calcula valor presente: `PV = Strike / (1 + CDI_diario)^n` onde `n` = dias úteis.
3. Exibe: valor a investir hoje, rentabilidade bruta em R$ e %, CDI implícito, dias corridos e úteis.
4. Botão "Copiar" para clipboard.

### Captura OCR (`_CaptureOverlay`)
**Garante:**
1. Janela fullscreen semi-transparente com cursor crosshair.
2. Usuário arrasta para selecionar região da tela.
3. OCR via `pytesseract` (Tesseract em `C:\Program Files\Tesseract-OCR\tesseract.exe`).
4. Imagem: grayscale, resize 3×, contraste 2×.
5. Config OCR: `--psm 7` (single line).
6. Resultado: texto limpo (sem espaços, quebras de linha).
7. ESC fecha sem capturar.

### `_read_taxa_cdi(db_path) -> float`
**Garante:**
1. Lê `taxa_cdi` do `ParametroRepository`.
2. Usada por ambas as abas como taxa anual padrão.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `datetime` | `date, timedelta` | Datas |
| `PySide6.QtWidgets` | `QApplication, QDialog, QTabWidget, ..., QButtonGroup` | UI framework |
| `PySide6.QtCore` | `Qt, QRect, QPoint` | Geometria |
| `PySide6.QtGui` | `QPainter, QColor, QCursor, QPen` | Overlay OCR |
| `src.domain.services.calculadora_colar` | `CalculadoraColar` | Black-Scholes |
| `src.domain.services.calendario_b3` | `dc_to_du` | Dias úteis |
| `src.infrastructure.persistence.database` | `get_connection` | (importado, uso não localizado no trecho lido) |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Taxa CDI |
| `src.ui.desktop.theme` | `Palette` | Cores |
| `pytesseract` | (config no topo) | OCR |

## Métricas

| Linhas | 562 |
| Classes | 3 (`_CaptureOverlay`, `BlackScholesWidget`, `CdiWidget`) + 1 principal (`CalculadorasDialog`) |
| Testes | Não |

## Notas

- **Tesseract hardcoded:** `pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'` — caminho Windows absoluto. Se Tesseract não estiver instalado ou em outro path, a captura OCR falha silenciosamente (captura retorna string vazia).
- **`get_connection` importado mas uso não confirmado** — provavelmente usado nas abas (não visível no trecho inicial do arquivo).
- **OCR com `ImageGrab.grab(bbox=..., all_screens=True)`:** Captura de múltiplos monitores. Depende de `Pillow` (PIL).
- **Fallback de taxa CDI:** Hardcoded `0.1425` (14.25%) como fallback — mas o código atual lê do banco. O fallback hardcoded foi removido conforme docstring, mas verifique se não há resquício.
