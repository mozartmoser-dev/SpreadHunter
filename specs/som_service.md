# SomService

Serviço de notificação sonora para alertas de oportunidades. Suporta três canais independentes (geral, vendidas, venda coberta), cada um com arquivo WAV configurável e volume ajustável. Fallback para `winsound.Beep` quando o arquivo WAV não é encontrado. Cache de arquivos processados para evitar re-geração a cada toque.

## Contrato (Requisitos)

### `tocar(db_path=None)`
**Garante:**
1. Toca o som "geral" (prefixo `"som"`).
2. Usa cache global `_CACHE_PATH`, `_CACHE_VOLUME`, `_CACHE_DB_PATH`, `_CACHE_FILE`.

### `tocar_vendidas(db_path=None)`
**Garante:**
1. Toca o som "vendidas" (prefixo `"som_vendidas"`).
2. Usa cache global com sufixo `_V`.

### `tocar_coberta(db_path=None)`
**Garante:**
1. Toca o som "coberta" (prefixo `"som_coberta"`).
2. Usa cache global com sufixo `_C`.

### `testar(db_path)`, `testar_vendidas(db_path)`, `testar_coberta(db_path)`
**Garante:**
1. Versões de teste que ignoram o cache (sempre recarregam parâmetros e reprocessam WAV).

### `_carregar_params(db_path, prefix="som", forcar_cache=False) -> tuple[str, float]`
**Garante:**
1. Instancia `ParametroRepository` e busca `som_arquivo{suffix}` e `som_volume{suffix}`.
2. `suffix` é `""` para geral, `"_vendidas"` para vendidas, `"_coberta"` para coberta.
3. `volume` é dividido por 100 (parâmetro 0-100 → float 0.0-1.0).
4. Se `forcar_cache=True`, invalida o cache do repositório antes de ler.
5. Se `arquivo` for `float` (valor numérico mal parseado), força string vazia.
6. Retorna `(arquivo, volume)`.

### `_gerar_wav_volume(orig_path: str, volume: float) -> str`
**Garante:**
1. Abre WAV original com `wave.open`.
2. Lê parâmetros e samples.
3. Suporta `sampwidth` 1, 2 e 4 bytes.
4. Aplica gain `volume` (0.0-1.0) aos samples.
5. Escreve WAV temporário com `tempfile.NamedTemporaryFile(suffix=".wav", delete=False)`.
6. Retorna path do arquivo temporário.

### `_tocar_wav(wav_path: str)`
**Garante:**
1. Usa `QMediaPlayer` + `QAudioOutput` do PySide6.
2. Executa `QEventLoop` bloqueante até `EndOfMedia` ou erro.
3. Timeout de 10s via `QTimer.singleShot`.

### `_tocar_premio(db_path, prefix, cache_tuple)`
**Garante:**
1. Carrega parâmetros com `forcar_cache=True` (sempre lê do banco).
2. Se arquivo existe e cache bate (mesmo path, volume, db_path), reusa WAV já processado.
3. Se cache não bate, gera novo WAV com volume, toca, e atualiza cache.
4. Se arquivo não existe, fallback para `winsound.Beep`:
   - Geral: 1000Hz/200ms + 1200Hz/150ms
   - Vendidas: 600Hz/300ms
   - Coberta: 800Hz/200ms + 1000Hz/150ms
5. Cache usa variáveis globais separadas por canal.

## Dependências Diretas (por import)

| Módulo | Símbolo | Uso |
|--------|---------|-----|
| `logging` | `logging` | Logger |
| `struct` | `struct` | Pack/unpack de samples WAV |
| `tempfile` | `tempfile` | Arquivo WAV temporário |
| `wave` | `wave` | Leitura/escrita WAV |
| `pathlib` | `Path` | Verificação de existência de arquivo |
| `PySide6.QtMultimedia` (runtime) | `QMediaPlayer`, `QAudioOutput` | Playback de áudio |
| `PySide6.QtCore` (runtime) | `QUrl`, `QEventLoop`, `QTimer` | Loop de eventos |
| `winsound` (runtime) | `winsound` | Fallback beep |
| `src.infrastructure.persistence.repositories.repositories` (runtime) | `ParametroRepository` | Leitura de parâmetros |

## Métricas

| Campo | Valor |
|-------|-------|
| Linhas | 212 |
| Última modificação | 2026-07-05 |
| Classes | 0 (módulo de funções) |

## Notas

- 2026-07-05 — última modificação.
- O uso de variáveis globais para cache (6 variáveis: `_CACHE_PATH`, `_CACHE_VOLUME`, `_CACHE_DB_PATH`, `_CACHE_FILE` × 3 canais) é um padrão de módulo singleton. Não é thread-safe — se duas threads chamarem `tocar()` simultaneamente, pode haver race condition no cache e no arquivo temporário.
- `QEventLoop` bloqueante em `_tocar_wav`: como o som service é chamado de dentro do `MonitorWorker` (QThread), criar um event loop aninhado pode causar problemas se houver eventos pendentes na fila. POSSÍVEL BUG — NÃO CORRIGIDO, aguardando revisão: `loop.exec_()` bloqueia a thread do worker durante o playback (até 10s), potencialmente atrasando o próximo ciclo de varredura.
- O fallback `winsound.Beep` é Windows-only. Consistente com o fato do sistema ser Windows-only.
- `_carregar_params` força `arquivo` para string vazia se o valor for `float`. Isso acontece quando o parâmetro no banco é numérico mas o código espera string (path do arquivo).
- Arquivos temporários (`delete=False`) nunca são limpos — acumulam no diretório temp do Windows ao longo de múltiplas execuções.
