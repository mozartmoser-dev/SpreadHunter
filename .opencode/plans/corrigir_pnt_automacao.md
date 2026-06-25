# Prompt: Correção PNT Automation (SwitchToThisWindow + acento)

## Contexto

A automação PNT (`executar_automacao_pnt()`) está rodando mas o teclado vai
para o terminal em vez do PNT porque `SetForegroundWindow` falha no Windows
moderno (restrição de segurança para processos background).

O código atual retorna "Sucesso" falso — o `Tab` + digitação + `Ctrl+V` são
enviados para o terminal sem lançar exceção.

## O que NÃO está quebrado (não mexer)

- `_minimizar_vscode()` — funciona
- `_minimizar_outras_janelas()` — funciona
- `_achar_janela_pnt()` — acha o HWND
- `_localizar_imagem()` — funciona
- `_selecionar_item_combobox()` com fallback — ok (não é mais usado)
- `_abrir_importacao_basket()` via Win32 API — funciona
- `boleta_dialog.py` — botão "Monta no PNT" adicionado, ok
- `test_pnt_automacao.py` — ok
- 279/279 testes passam

## Correções necessárias (SOMENTE 3 linhas)

### Arquivo: `src/infrastructure/integrations/pnt.py`

**1.** No topo do arquivo (entre `import logging` e `from pathlib`),
adicionar:

```python
import ctypes
```

**2.** Em `_focar_janela_pnt()` (~linha 278), trocar:

```python
                    win32gui.SetForegroundWindow(hwnd)
```

por:

```python
                    ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
```

`SwitchToThisWindow` é a única API do Windows que funciona de processo
background no Windows 10/11 moderno. `SetForegroundWindow` tem restrição
de segurança que sempre falha quando chamado de script Python.

**3.** Na digitação do dropdown (~linha 427), trocar:

```python
                        pyautogui.write("Robo - MultiLeg (ativo por coluna)", interval=0.05)
```

por:

```python
                        pyautogui.write("Robô - MultiLeg (ativo por coluna)", interval=0.05)
```

O acento em "Robô" é **crítico** — o autocomplete do PNT só encontra o
item se o texto for EXATAMENTE igual ao que está no dropdown.

Referência completa dos itens do dropdown em:
`src/infrastructure/integrations/pnt_images/OPCOES_DROPDOWN.md`

## Fluxo esperado após a correção

1. `executar_automacao_pnt()` é chamado
2. `_minimizar_vscode()` minimiza VS Code
3. `_focar_janela_pnt()` → `SwitchToThisWindow` traz PNT pra frente ✅
4. `_abrir_importacao_basket()` via Win32 API → dialog abre ✅
5. `Tab` → foco no dropdown
6. `pyautogui.write("Robô - MultiLeg (ativo por coluna)")` → item selecionado
7. `Enter` → confirma
8. `Tab` → foco na grade
9. `Ctrl+V` → basket colado ✅

## Como testar

```bash
python test_pnt_automacao.py
```

Observar: o PNT deve ir para primeiro plano antes do Tab.

## Rollback (se algo quebrar)

```bash
git checkout -- src/infrastructure/integrations/pnt.py
```

Isso reverte o arquivo para a última versão commitada.

## Notas importantes

- A sequência não usa mais imagem reconhecimento (foi substituído por Win32
  API + teclado)
- Evitar mexer em qualquer outra parte do arquivo
- O botão "Monta no PNT" em `boleta_dialog.py` chama `_montar_pnt()` que
  copia o basket e dispara `executar_automacao_pnt()`
