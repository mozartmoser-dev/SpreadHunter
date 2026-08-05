# Prompt original da sessão OpenSpec — 04/08/2026

Você é um Arquiteto de Software Principal, especialista em sistemas quantitativos em Python
para trading de opções (B3). Baseado em `specs/inventory.md` (já aprovado), vamos gerar as
specs de módulo individuais do projeto Spreadhunter, seguindo a metodologia OpenSpec.

REGRA DE ATOMICIDADE — a mais importante deste prompt
Trabalhe em APENAS 1 módulo por vez, na ordem exata da lista abaixo. Depois de gerar a spec
de um módulo: PARE a execução. Não avance para o próximo módulo da lista automaticamente.
Aguarde minha confirmação explícita ("aprovado, siga para o próximo") antes de começar o
módulo seguinte.

ORDEM DE GERAÇÃO
1. ParametroRepository
2. CalculadoraProtecaoCauda
3. CalculadoraCaudaAssincrona
4. InstrumentoRepository
(após aprovação das 4 acima, retomamos com o restante da Camada 2, depois Camada 1
restante, depois Camada 3)

FORMATO DE CADA SPEC
Gerar em `specs/<nome_do_modulo_em_snake_case>.md`, com estas seções obrigatórias:
- Propósito (2-4 frases, intenção de negócio)
- Contrato (Requisitos) — o que o módulo GARANTE, fórmulas exatas com unidades
- Decisões Tomadas — com o "porquê" baseado em histórico real
- Decisões Rejeitadas — alternativas descartadas com motivo
- Dependências
- Cobertura de Teste — status + lacunas conhecidas

RESTRIÇÕES
- Somente leitura de código-fonte — não altere nenhum arquivo além de criar os novos em specs/.
- Se decisão/motivo não estiver claro, marcar como "[motivo não documentado no código, confirmar com o autor]".
- Ao final de CADA módulo, gerar resumo curto no chat.
