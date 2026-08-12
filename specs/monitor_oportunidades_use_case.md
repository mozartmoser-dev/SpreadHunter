# MonitorOportunidadesUseCase

## Propósito

Primeiro estágio do pipeline do worker ("Geral"). Carrega TODOS os instrumentos do banco,
usa `CalculadoraVetorizada` para filtrar pares viáveis e **montar diretamente os DTOs**
de forma 100% vetorizada com numpy — classificação, operação e todos os 38 campos do
`OportunidadeMonitor` são derivados dos arrays vetorizados, sem processamento individual.
O método `_calcular_oportunidade` (OO) não é mais chamado no fluxo principal.

Gera `OportunidadeMonitor` (DTO da tabela principal) e, se Telegram habilitado, monta e
envia notificações.

## Dependências

- `numpy`
- `src.domain.services.calculadora_box_sbth` → `CalculadoraBoxSbth`, `DadosMercado`
- `src.domain.services.calculadora_vetorizada` → `CalculadoraVetorizada`
- `src.domain.services.pipeline_tracker` → `PipelineTracker`
- `src.infrastructure.persistence.repositories.repositories` → `InstrumentoRepository`, `ParametroRepository`
- `src.infrastructure.notifications.telegram_service` → `TelegramService`
- `src.application.dtos.dtos` → `OportunidadeMonitor`

## Cobertura de Teste

**Status: 7 testes** (5 em `test_fase3.py` + 2 em `test_telegram_msg.py`). Inventory.md classifica como "Sim".
