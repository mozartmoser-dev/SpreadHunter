# Distribuição — Build PyInstaller

## Pré-requisitos

| Item | Versão |
|------|--------|
| Python | 3.13.x (`C:\Program Files\Python313\python.exe`) |
| PyInstaller | 6.21.0 |
| Dependências | `pip install -e .` (ou o que estiver em `pyproject.toml`) |

## Build

```powershell
# Do diretório raiz do projeto:
python -m PyInstaller --clean ^
    --distpath "%USERPROFILE%\Desktop\dist" ^
    --workpath "%USERPROFILE%\Desktop\build_pyi" ^
    spreadhunter.spec
```

Ou via script automatizado:

```powershell
powershell -File scripts/build_redistribuicao.ps1
```

### O que o script faz

1. Limpa `__pycache__` recursivamente no projeto
2. Roda PyInstaller com `spreadhunter.spec`
3. Move a saída para `Desktop/Spreadhunter/`
4. Gera `.env.example` e `INSTRUCOES.txt`
5. Compacta `Desktop/Spreadhunter_v0.1.0.zip`

### O que o script **NÃO** faz mais

~~Remove bancos do projeto~~ — linha deletada após apagar o DB do dev sem querer.

## Arquivos de build

| Arquivo | Função |
|---------|--------|
| `spreadhunter.spec` | Configuração do PyInstaller (hidden imports, excludes, runtime hooks) |
| `scripts/build_redistribuicao.ps1` | Automação completa (build + zip) |
| `scripts/runtime_hook.py` | Roda antes do `main.py`: seta matplotlib backend, cria `logs/`, adiciona DLL path do pywin32 |

## Cuidados

- **Build só mexe no Desktop, nunca no projeto.** A saída vai para `Desktop/dist/` e `Desktop/build_pyi/`, depois movida para `Desktop/Spreadhunter/`. O build **não apaga, não altera, não remove nada** dentro da pasta do projeto — nem bancos, nem configs, nem código, nem `__pycache__`.
- **Banco de dados**: o `.exe` gera o próprio DB em `Desktop/Spreadhunter/data/spreadhunter.db`. O DB do projeto não é afetado.
- **Ofuscação**: PyArmor trial não funciona (limite de tamanho de arquivo). Se precisar, comprar licença Pro (~$100).
- **Teste**: o build leva ~2min. O `.exe` abre ~8s na primeira vez. Testar com `Start-Process -WindowStyle Hidden` + `Wait` pra ver se crasha.

## Spec (`spreadhunter.spec`)

Pontos importantes:
- **ONE_DIR** (não um único .exe) — necessário por causa de DLLs do scipy/PySide6
- **Hidden imports**: `sqlite3`, `numpy.testing`, `unittest`, `PySide6.QtXml`, `win32clipboard`
- **Excludes**: `PIL`, `setuptools`, `pip`, `tkinter`, `IPython`, etc. (reduz tamanho)
- **Runtime hooks**: `scripts/runtime_hook.py` (custom) + hooks padrão do PyInstaller
- **Matplotlib backend**: `QtAgg` via runtime hook

## Troubleshooting

| Erro | Causa | Solução |
|------|-------|---------|
| `FileNotFoundError: logs/spreadhunter.log` | Runtime hook cria `logs/` no lugar errado | Deve ser `Path(sys.argv[0]).parent / "logs"`, não `_MEIPASS / "logs"` |
| `ModuleNotFoundError: sqlite3` | `sqlite3` excluído acidentalmente | Adicionar a `hiddenimports` no spec |
| `ModuleNotFoundError: unittest` | Scipy depende de `unittest` | Adicionar a `hiddenimports` |
| `scipy.special._cdflib not found` | Aviso benigno | Ignorar |
| PyArmor "big script" | Licença trial limita tamanho | Usar PyInstaller puro ou licença Pro |
| PyArmor + PyInstaller conflitam | Ofuscados precisam de `.py` no disco real | PyInstaller coloca no PYZ/archive |

### 🚧 RTD (Profit) não funciona no .exe compilado

**Sintoma**: `RTD ServerStart falhou — Profit precisa estar aberto.` no log. App mostra "RTD: OFF" mesmo com Profit aberto.

**Causa**: `win32com.server.util.wrap()` (registro de callback COM) não funciona em app congelado pelo PyInstaller. `ServerStart` com callback falha. `ServerStart(None)` também falha.

**O que já foi tentado** (23/06/2026):
- Remover o callback e tentar `ServerStart(None)` direto
- Marcar `disponivel = False` quando ServerStart falha (correção aplicada no código fonte)
- Adicionar `reconectar()` + retry automático no loop
- No ambiente dev (`python main.py`) funciona normalmente

**Próximas tentativas sugeridas**:
- Mover criação do `RTDProfit` para a thread principal (UI), não na worker thread
- Testar `CoInitializeEx(COINIT_MULTITHREADED)` em vez de `APARTMENTTHREADED`
- Executar o .exe como administrador (permissão COM)
- Verificar com o suporte do Profit se o RTD server precisa de configuração especial
- Alternativa: substituir RTD COM por leitura de arquivo ou named pipe do Profit

## Fluxo de distribuição

1. Rodar `scripts/build_redistribuicao.ps1`
2. Levar `Desktop/Spreadhunter_v0.1.0.zip` (ou o `.exe` avulso da pasta `Desktop/Spreadhunter/`)
3. O amigo extrai e executa `Spreadhunter.exe`
4. Na primeira execução o banco é criado automaticamente
5. Instruções completas dentro do `INSTRUCOES.txt` no zip

## Histórico

| Data | Versão | Mudança |
|------|--------|---------|
| 23/06/2026 | 0.1.0 | Build inicial PyInstaller puro (sem PyArmor). |
