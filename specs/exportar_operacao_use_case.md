# ExportarOperacaoUseCase

## Propósito

Exporta operações para dois formatos: Basket ITM (montagem de Box com CALL ITM para PNT)
e Log de Operação (registro de execução). Usa `MontadoraBoxItm` para construir a estrutura
de pernas (EstruturaOperacional + PernaOperacao) e persiste via repositories.

## Dependências

- `src.domain.entities.estrutura_operacional` → `EstruturaOperacional`, `TipoEstrutura`
- `src.domain.entities.oportunidade` → `Oportunidade`, `ClassificacaoOp`
- `src.domain.entities.perna_operacao` → `PernaOperacao`, `Lado`
- `src.domain.services.montadora_box_itm` → `MontadoraBoxItm`
- `src.infrastructure.importers.excel_importer` → `extrair_strike`
- `src.infrastructure.persistence.repositories.repositories` → `InstrumentoRepository`, `OportunidadeRepository`, `EstruturaRepository`, `PernaRepository`

## Cobertura de Teste

**Status: 11 testes** (3 em `test_fase3.py` + 8 em `test_exportar_csv_dtos.py`). Inventory.md classifica como "Parcial".
