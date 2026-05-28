# Histórico de Integração SpreadHunter ↔ PlugNTrade

**Data:** 22/05/2026
**Objetivo:** Automatizar o preenchimento de operações SBTH e BOX no PlugNTrade (PNT) ao clicar em "Registrar Operação" no SpreadHunter, sem alterar funcionalidades existentes.

---

## ✅ Acordos e Requisitos

### 1. **Comportamento esperado**
- Ao clicar em **"Registrar Operação"** no SpreadHunter:
  - A operação é salva no banco de dados (comportamento original mantido).
  - **Adicionalmente**, os dados da operação são enviados ao PlugNTrade via interface gráfica (não API).
- **SBTH** → abre tela **SPREAD** no PNT → preenche **Ativo + Put** (Call é implícito, **não preenchido**).
- **BOX** → abre tela **MULTILEG** no PNT → preenche **Ativo + Put + Call**.
- **Nenhum envio automático** — o usuário **sempre confirma manualmente** no PNT com `Enter`.

### 2. **Parâmetros de operação (armazenados no banco)**

| Chave | Descrição | Exemplo |
|-------|-----------|---------|
| `lote_ativo_sbth` | Lote do ativo na operação SBTH | `100` |
| `lote_put_sbth` | Lote da Put na operação SBTH | `100` |
| `profundidade_ativo_sbth` | Profundidade do ativo na SBTH | `0` |
| `profundidade_put_sbth` | Profundidade da Put na SBTH | `1` |
| `lote_ativo_box` | Lote do ativo na operação BOX | `200` |
| `lote_put_box` | Lote da Put na operação BOX | `200` |
| `lote_call_box` | Lote da Call na operação BOX | `200` |
| `profundidade_ativo_box` | Profundidade do ativo na BOX | `0` |
| `profundidade_put_box` | Profundidade da Put na BOX | `0` |
| `profundidade_call_box` | Profundidade da Call na BOX | `1` |

> Os parâmetros devem ser configurados manualmente via `ParametrosWidget` no SpreadHunter.

### 3. **Mecanismo de integração**
- **Não usar `tab` ou navegação por teclado** — instável e dependente de foco.
- **Usar localização por imagem** (`pyautogui.locateOnScreen`) para clicar **exatamente nos campos** do PNT.
- **Nenhum arquivo do PNT será alterado** — apenas simulação de clique + digitação.
- **Nenhum arquivo do SpreadHunter será modificado além da adição de uma única linha** em `export_dialog.py`.

---

## 📁 Estrutura de Arquivos Criada

```
Spreadhunter/
├── scratch/
│   └── pnt_fields/
│       ├── ativo.png
│       ├── lote_ativo.png
│       ├── profundidade_ativo.png
│       ├── strike_put.png
│       ├── lote_put.png
│       ├── profundidade_put.png
│       ├── strike_call.png
│       ├── lote_call.png
│       └── profundidade_call.png
├── src/
│   └── infrastructure/
│       └── integrations/
│           └── pnt.py          ← Lógica de integração
└── src/ui/desktop/export_dialog.py ← Adicionada linha: self._enviar_para_pnt()
```

---

## 🚫 O que NÃO foi feito (por decisão do usuário)

- **Não foi gerado nenhum arquivo `opencode.json`** — fora do escopo.
- **Não foi feita nenhuma alteração em arquivos existentes além do necessário**.
- **Não foi usado `pyautogui.press('tab')`** — substituído por clique por imagem.
- **Não foi executado qualquer script no PNT real** — apenas simulação.

---

## 📌 Próximos Passos (para segunda-feira)

1. ✅ **Você irá fornecer as 9 imagens recortadas** (`ativo.png`, `lote_ativo.png`, etc.) com os campos exatos do PNT na sua tela.
1. ✅ **O ponto de partida é o foco automático**: A boleta do PNT já abre com o foco no campo Ativo, eliminando a necessidade de âncora visual (`ativo.png`).
2. ❌ **Coordenadas fixas descartadas**: A navegação será 100% via teclado (Tabs) a partir do foco inicial, garantindo maior estabilidade.
3. ✅ **Eu atualizarei o `pnt.py`** para usar **suas imagens e coordenadas** — garantindo precisão absoluta.
4. ✅ **Mapeamento Confirmado**: Ativo na Linha 1, Put na 2 e Call na 3.
5. ✅ **Abordagem Híbrida**: Imagem para âncora + Tabs para colunas.
6. ✅ **Validação de Tabs**: Sequência de 9 Tabs mapeada para preenchimento e transição de linhas.
7. ✅ **Ajuste de Fluxo**: Ao marcar 'Compra', o PNT pula automaticamente a caixa de Venda. Campo 8 é pulado e Campo 9 preenche o próximo ticker.
8. **Se aprovado, a integração será liberada** para uso diário.
6. ✅ **Validação de Tabs**: Sequência de 28 Tabs mapeada para preenchimento completo.
7. ✅ **Ajuste de Fluxo**: Refinamento dos Tabs 4, 5, 6, 8, 10 e 23 conforme comportamento da grade.
8. ✅ **Finalização**: Inclusão do campo de Custo (Diferença Ponderada) e Mínima Apregoada.
9. ✅ **Script de Teste**: Criado `scratch/test_pnt_ui_automation.py` para validação visual sem dependência de banco de dados.
10. **Se aprovado, a integração será liberada** para uso diário.

---

> ✅ Este documento foi gerado para ser usado como base de referência na próxima sessão. Não será alterado automaticamente. Você pode editá-lo manualmente antes de passar para mim na segunda-feira.