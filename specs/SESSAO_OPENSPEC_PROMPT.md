# Prompt da sessão OpenSpec — 05/08/2026 (v2)

Você é um Arquiteto de Software Principal, especialista em sistemas quantitativos em Python para trading de opções (B3). Baseado em specs/inventory.md (já aprovado), vamos gerar as specs de módulo individuais do projeto Spreadhunter, seguindo a metodologia OpenSpec.

============================================================ REGRA DE ATOMICIDADE — a mais importante deste prompt

Trabalhe em APENAS 1 módulo por vez, na ordem exata da lista abaixo. Depois de gerar a spec de um módulo:

PARE a execução.
Não avance para o próximo módulo da lista automaticamente.
Aguarde minha confirmação explícita ("aprovado, siga para o próximo") antes de começar o módulo seguinte.

Motivo: specs geradas em lote, sem revisão intermediária, tendem a acumular inconsistência e alucinação de detalhes entre módulos distantes do código real — cada módulo precisa ser conferido contra o código-fonte antes do próximo começar.

============================================================ ORDEM DE GERAÇÃO
1. ParametroRepository — ✅ CONCLUÍDO (specs/parametro_repository.md)
2. CalculadoraProtecaoCauda — ✅ CONCLUÍDO (specs/calculadora_protecao_cauda.md)
3. CalculadoraCaudaAssincrona — 🔜 PRÓXIMO
4. InstrumentoRepository
(após aprovação das 4 acima, retomamos com o restante da Camada 2, depois Camada 1 restante, depois Camada 3)

============================================================ FORMATO DE CADA SPEC

Gerar em specs/<nome_do_modulo_em_snake_case>.md, com estas seções obrigatórias:

Propósito — O que o módulo faz e por que existe, em 2-4 frases. Não é documentação de API, é a intenção de negócio por trás dele.

Contrato (Requisitos) — Lista do que o módulo GARANTE — comportamentos que não podem quebrar silenciosamente numa refatoração futura. Para cálculos financeiros, incluir a fórmula exata como contrato verificável (não só descrição em prosa), com as UNIDADES explícitas (ex: "valor por ação" vs "valor total do portfólio" — isso já causou um bug de escala real neste projeto).

Decisões Tomadas — Para cada decisão de design não-óbvia, registrar: o que foi decidido, e POR QUÊ (não só o quê). Use o histórico de conversas/commits reais do projeto como fonte — não invente justificativa genérica.

Decisões Rejeitadas — Alternativas que foram consideradas e descartadas, com o motivo. Isso existe para impedir que a mesma alternativa seja proposta de novo no futuro sem saber que já foi tentada.

Dependências — Lista as dependências diretas (já estão em inventory.md, só repita aqui para a spec ser autocontida).

Cobertura de Teste — Status atual (puxar de inventory.md) e, se houver lacuna conhecida, apontar explicitamente o que não está coberto.

============================================================ CONTEXTO ESPECÍFICO POR MÓDULO
CalculadoraCaudaAssincrona

Contrato crítico a travar: os termos incrementais do grid de ratio ((n-1) * extra_call_pnl e (1-m) * custo_put) DEVEM ser multiplicados por qtd_acao antes de somar a pnl_projetado_base. REGISTRAR COMO BUG HISTÓRICO CORRIGIDO: a versão original não fazia essa multiplicação, fazendo o termo incremental entrar ~1000x menor que o correto (confundindo valor "por ação" com valor "de portfólio inteiro") — isso mascarava quase todo o efeito da otimização de ratio até ser descoberto e corrigido. Este contrato existe especificamente para essa fórmula nunca regressar nesse estado numa refatoração futura.

InstrumentoRepository — [contexto a ser preenchido quando chegar a vez]

============================================================ RESTRIÇÕES
- Somente leitura de código-fonte — não altere nenhum arquivo além de criar os novos em specs/.
- Se alguma decisão/motivo não estiver claro, marque como "[motivo não documentado no código, confirmar com o autor]".
- DEPENDÊNCIAS SÓ POR EVIDÊNCIA DIRETA NO PRÓPRIO ARQUIVO: confirme rodando grep dos imports antes de escrever a seção.
- Ao final de CADA módulo, gere resumo curto no chat com: o que foi capturado, e qualquer ponto que você não teve certeza.
