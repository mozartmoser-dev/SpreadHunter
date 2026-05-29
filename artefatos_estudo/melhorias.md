# Plano de Melhorias - SpreadHunter

Este documento detalha as oportunidades de melhoria identificadas após a análise da arquitetura atual e do histórico de integração.

## 1. Robustez da Integração com PlugNTrade (PNT)
*   **Abstração de Coordenadas:** Atualmente, a automação depende de scripts de calibração manuais e imagens específicas (`pnt_fields/`). 
    *   *Sugestão:* Criar um arquivo de configuração `pnt_config.json` que armazene offsets e níveis de confiança por resolução de tela, evitando que o código precise ser alterado quando o usuário mudar de monitor.
*   **Migração de PyAutoGUI para Win32 API:** O `pyautogui` simula o mouse de forma "cega". 
    *   *Sugestão:* Investigar o uso da biblioteca `pywinauto` ou `pywin32`. Se o PNT for uma aplicação nativa Windows (Delphi/C++), é possível enviar comandos diretamente para os IDs dos controles (botões/grids), tornando a integração 10x mais rápida e imune a janelas sobrepostas.
*   **Fallback de Clipboard:** A automação de "Colar" (`Ctrl+V`) pode falhar se o usuário interagir com o teclado.
    *   *Sugestão:* Implementar um semáforo ou trava de interface que avise o usuário: "Registrando operação, aguarde..." para evitar conflitos de input.

## 2. Performance e Infraestrutura de Dados
*   **Otimização do Crawler de Opções:** O estudo em `estudo_base_opcoes.md` já identificou o caminho. 
    *   *Sugestão:* Substituir o bot Playwright por requisições `requests` diretas nos endpoints AJAX do `opcoes.net.br`. Isso reduzirá o consumo de memória (sem navegador aberto) e o tempo de atualização da base de minutos para segundos.
*   **Gargalo do RTD:** O RTD do Profit/PNT é síncrono e trava a UI se muitos tickers forem monitorados.
    *   *Sugestão:* Implementar um padrão *Observer* com `QThread` no PyQt para que o processamento dos dados em tempo real ocorra fora da thread principal da interface.

## 3. Qualidade de Código e Manutenibilidade
*   **Unificação de Ferramentas (Scratch):** Há muitos scripts dispersos na pasta `scratch/`.
    *   *Sugestão:* Consolidar `calibrar_botao_colar.py`, `cut_pnt_fields.py` e `discover_pnt_import.py` em uma CLI de ferramentas de desenvolvedor (`python manage.py tools calibrate`), facilitando o setup em novas máquinas.
*   **Tratamento de Exceções na Calculadora:** O histórico mostra ajustes manuais frequentes em fórmulas de PnL.
    *   *Sugestão:* Adicionar testes unitários (`pytest`) especificamente para a `CalculadoraColarCalendario`, garantindo que novos cenários de exercício não quebrem a lógica de lucro/prejuízo já validada.

## 4. Experiência do Usuário (UX)
*   **Feedback Visual de Automação:** Quando o `pnt.py` executa, o usuário não sabe se o script terminou ou falhou silenciosamente.
    *   *Sugestão:* Adicionar um pequeno Overlay ou mudar a cor do botão "Registrar Operação" para amarelo (em progresso) e verde/vermelho (sucesso/erro) após a tentativa de envio ao PNT.
*   **Cache Seletivo:** 
    *   *Sugestão:* Implementar um cache local (SQLite) para as opções de ativos favoritos (PETR4, VALE3), evitando reprocessar toda a base de instrumentos a cada abertura do diálogo.

## 6. Documentação e Assistência de IA
*   **Uso de Arquivos de Sugestões:** Adotar o uso de extensões como Cline ou Continue para manter este arquivo (`melhorias.md`) atualizado automaticamente após cada grande refatoração.
*   **Sincronização de Worker:** Corrigida falha no `monitor_worker.py` onde chamadas de métodos de varredura estavam órfãs. Implementada modularização para facilitar a manutenção de novas estratégias.

## 5. Próximos Passos Prioritários (MVP 2.0)
1. Implementar o Crawler AJAX (Adeus Playwright).
2. Mapear IDs de controles do PNT via Inspect.exe para substituir cliques por imagem.
3. Adicionar logs rotativos para depurar falhas de integração no ambiente de produção.