# RegrasDialog

Diálogo que exibe as regras ativas e filtros de uma estratégia específica. Combina três fontes de informação: (1) ordem de filtros lida dinamicamente do código fonte dos use cases, (2) parâmetros com valores atuais do banco de dados, e (3) regras estruturais fixas (fórmulas, definições).

Os dicionários `_FILTROS_POR_ESTRATEGIA`, `_REGRAS_ESTRUTURAIS` e `_REGRAS_PARAM_MAP` são definidos no nível do módulo e servem como documentação viva das regras de negócio de cada estratégia.

## Contrato (Requisitos)

### `RegrasDialog(estrategia, db_path, parent) -> None`
**Garante:**
1. Título "Regras Ativas — {estrategia}" com tamanho mínimo 580×400.
2. Exibe custos fixos B3 (`_CUSTOS_FIXOS`) em destaque amarelo.
3. Tabela de parâmetros do DB com 3 colunas: Parâmetro, Valor Atual, Descrição.
4. Seção de regras do código-fonte montada por `_montar_regras_codigo()`.

### `_popular_tabela(tabela) -> None`
**Garante:**
1. Lê parâmetros da estratégia específica via `repo.get_by_estrategia(self._estrategia)`.
2. Para estratégias não-GERAL, também inclui parâmetros GERAL relevantes: `taxa_cdi`, `taxa_emolumento_pct`, `taxa_liquidacao_pct`, `taxa_registro_pct`, `taxa_iss_pct`, `taxa_ir_pct`.
3. Ordena alfabeticamente por chave.

### `_montar_regras_codigo() -> str`
**Garante:**
1. Se existirem filtros dinâmicos em `_FILTROS_POR_ESTRATEGIA`, exibe a ordem dos filtros primeiro.
2. Preenche templates de `_REGRAS_PARAM_MAP` com valores atuais do banco (formatação condicional: `x CDI` → 2 casas, `%` → ×100, otherwise raw).
3. Adiciona regras estruturais fixas de `_REGRAS_ESTRUTURAIS`.
4. Se nenhuma regra documentada: retorna mensagem padrão.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|---|---|---|
| `PySide6.QtWidgets` | `QDialog`, `QVBoxLayout`, `QHBoxLayout`, `QPushButton`, `QLabel`, `QTableWidget`, `QTableWidgetItem`, `QHeaderView`, `QMessageBox` | UI do diálogo |
| `PySide6.QtCore` | `Qt` | Alinhamento |
| `PySide6.QtGui` | `QFont` | Fonte Consolas para valores |
| `src.ui.desktop.theme` | `Palette` | Cores do tema |
| `src.domain.entities.parametro_operacional` | `ParametroOperacional` | Importado mas não usado diretamente no código (parâmetros vêm do repo como dict) |
| `src.application.use_cases.monitor_colares_calendario` | `FILTROS_COLLAR_CALENDARIO` | (Import dinâmico, try/except) |
| `src.application.use_cases.monitor_colares` | `FILTROS_COLAR` | (Import dinâmico, try/except) |
| `src.infrastructure.persistence.repositories.repositories` | `ParametroRepository` | Import lazy dentro de `_popular_tabela` e `_montar_regras_codigo` |

## Métricas

| Linhas | 278 |
| Testes | Não |

## Notas

- **Data da última modificação:** 2026-07-09
- Apenas duas estratégias têm filtros dinâmicos documentados: `COLLAR_CALENDARIO` e `COLAR`. As demais dependem apenas de `_REGRAS_ESTRUTURAIS` e `_REGRAS_PARAM_MAP`.
- `_REGRAS_PARAM_MAP` cobre apenas BOX, SBTH, COLAR, COLLAR_CALENDARIO e BOX_4P. Estratégias como PUT_RATIO, MPP, PROTECAO_CAUDA, VENDA_COBERTA têm apenas regras estruturais.
- `ParametroRepository` é importado lazy (dentro dos métodos), não no topo do arquivo. Isso é intencional para evitar import circular com o módulo de repositórios.
- `ParametroOperacional` é importado no topo mas parece ser usado apenas como type hint implícito — os valores reais vêm como dict do repositório.
- `_CUSTOS_FIXOS` tem um erro de digitação: "Liquidacao" em vez de "Liquidação".
