# ColetarTaxasAluguelUseCase

## Propósito

Coleta taxas de aluguel de ações do InvestSite (web scraping) para todos os ativos
no `InstrumentoRepository`. Insere no banco via `TaxaAluguelRepository` com
`ON CONFLICT(ativo, data) DO UPDATE`.

## Dependências

- `src.domain.entities.taxa_aluguel` → `TaxaAluguel`
- `src.infrastructure.integrations.investsite_client` → `InvestSiteClient`
- `src.infrastructure.persistence.repositories.repositories` → `InstrumentoRepository`, `TaxaAluguelRepository`

## Cobertura de Teste

**Status: 2 testes** em `test_investsite_coleta.py`. Inventory.md classifica como "Parcial".
