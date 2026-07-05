import logging
import struct
import tempfile
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_PATH = None
_CACHE_VOLUME = None
_CACHE_DB_PATH = None
_CACHE_FILE = None

_CACHE_PATH_V = None
_CACHE_VOLUME_V = None
_CACHE_DB_PATH_V = None
_CACHE_FILE_V = None

_CACHE_PATH_C = None
_CACHE_VOLUME_C = None
_CACHE_DB_PATH_C = None
_CACHE_FILE_C = None


def _carregar_params(db_path, prefix="som", forcar_cache=False):
    from src.infrastructure.persistence.repositories.repositories import ParametroRepository

    repo = ParametroRepository(db_path)
    if forcar_cache:
        repo.invalidate_cache()
    if prefix == "som_vendidas":
        suffix = "_vendidas"
    elif prefix == "som_coberta":
        suffix = "_coberta"
    else:
        suffix = ""
    arquivo_p = repo.get_by_chave(f"som_arquivo{suffix}")
    volume_p = repo.get_by_chave(f"som_volume{suffix}")

    arquivo = arquivo_p.valor if arquivo_p else ""
    volume = float(volume_p.valor) / 100.0 if volume_p else 1.0

    if isinstance(arquivo, float):
        arquivo = ""
    arquivo = str(arquivo).strip()
    return arquivo, volume


def _gerar_wav_volume(orig_path: str, volume: float) -> str:
    with wave.open(orig_path, "rb") as wf:
        params = wf.getparams()
        nframes = params.nframes
        nchannels = params.nchannels
        sampwidth = params.sampwidth
        raw = wf.readframes(nframes)

    if sampwidth == 1:
        fmt = f"<{nframes * nchannels}b"
    elif sampwidth == 2:
        fmt = f"<{nframes * nchannels}h"
    elif sampwidth == 4:
        fmt = f"<{nframes * nchannels}i"
    else:
        fmt = f"<{nframes * nchannels}h"

    samples = struct.unpack(fmt, raw)
    gain = max(0.0, min(1.0, volume))
    scaled = struct.pack(fmt, *[int(s * gain) for s in samples])

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setparams(params)
        wf.writeframes(scaled)

    return tmp.name


def _tocar_wav(wav_path: str):
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtCore import QUrl, QEventLoop, QTimer

    loop = QEventLoop()
    player = QMediaPlayer()
    audio = QAudioOutput()
    player.setAudioOutput(audio)
    player.setSource(QUrl.fromLocalFile(wav_path))

    player.mediaStatusChanged.connect(
        lambda s: loop.quit() if s == QMediaPlayer.EndOfMedia else None
    )
    player.errorOccurred.connect(lambda e: loop.quit())

    QTimer.singleShot(10000, loop.quit)

    player.play()
    loop.exec_()


def _tocar_premio(db_path, prefix, cache_tuple):
    global _CACHE_PATH, _CACHE_VOLUME, _CACHE_DB_PATH, _CACHE_FILE
    global _CACHE_PATH_V, _CACHE_VOLUME_V, _CACHE_DB_PATH_V, _CACHE_FILE_V
    global _CACHE_PATH_C, _CACHE_VOLUME_C, _CACHE_DB_PATH_C, _CACHE_FILE_C

    cache_path, cache_volume, cache_db, cache_file = cache_tuple
    arquivo, volume = _carregar_params(db_path, prefix, forcar_cache=True) if db_path else ("", 1.0)

    if arquivo and Path(arquivo).exists():
        if cache_path == arquivo and cache_volume == volume and cache_db == db_path and cache_file:
            try:
                _tocar_wav(cache_file)
            except Exception:
                pass
            return

        try:
            tmp = _gerar_wav_volume(arquivo, volume)
            _tocar_wav(tmp)
            if prefix == "som_coberta":
                _CACHE_PATH_C, _CACHE_VOLUME_C, _CACHE_DB_PATH_C, _CACHE_FILE_C = arquivo, volume, db_path, tmp
            elif prefix == "som_vendidas":
                _CACHE_PATH_V, _CACHE_VOLUME_V, _CACHE_DB_PATH_V, _CACHE_FILE_V = arquivo, volume, db_path, tmp
            else:
                _CACHE_PATH, _CACHE_VOLUME, _CACHE_DB_PATH, _CACHE_FILE = arquivo, volume, db_path, tmp
            return
        except Exception as e:
            logger.warning("Falha ao tocar %s: %s. Usando beep.", arquivo, e)

    import winsound

    if prefix == "som_coberta":
        winsound.Beep(800, 200)
        winsound.Beep(1000, 150)
    elif prefix == "som_vendidas":
        winsound.Beep(600, 300)
    else:
        winsound.Beep(1000, 200)
        winsound.Beep(1200, 150)


def tocar(db_path=None):
    _tocar_premio(db_path, "som", (_CACHE_PATH, _CACHE_VOLUME, _CACHE_DB_PATH, _CACHE_FILE))


def tocar_vendidas(db_path=None):
    _tocar_premio(db_path, "som_vendidas", (_CACHE_PATH_V, _CACHE_VOLUME_V, _CACHE_DB_PATH_V, _CACHE_FILE_V))


def tocar_coberta(db_path=None):
    _tocar_premio(db_path, "som_coberta", (_CACHE_PATH_C, _CACHE_VOLUME_C, _CACHE_DB_PATH_C, _CACHE_FILE_C))


def testar(db_path):
    global _CACHE_PATH, _CACHE_VOLUME, _CACHE_FILE

    arquivo, volume = _carregar_params(db_path, "som", forcar_cache=True)

    if arquivo and Path(arquivo).exists():
        try:
            tmp = _gerar_wav_volume(arquivo, volume)
            _tocar_wav(tmp)
            _CACHE_PATH = arquivo
            _CACHE_VOLUME = volume
            _CACHE_FILE = tmp
            return
        except Exception as e:
            logger.warning("Falha ao testar %s: %s", arquivo, e)

    import winsound

    winsound.Beep(800, 300)


def testar_vendidas(db_path):
    global _CACHE_PATH_V, _CACHE_VOLUME_V, _CACHE_FILE_V

    arquivo, volume = _carregar_params(db_path, "som_vendidas", forcar_cache=True)

    if arquivo and Path(arquivo).exists():
        try:
            tmp = _gerar_wav_volume(arquivo, volume)
            _tocar_wav(tmp)
            _CACHE_PATH_V = arquivo
            _CACHE_VOLUME_V = volume
            _CACHE_FILE_V = tmp
            return
        except Exception as e:
            logger.warning("Falha ao testar vendidas %s: %s", arquivo, e)

    import winsound

    winsound.Beep(800, 300)


def testar_coberta(db_path):
    global _CACHE_PATH_C, _CACHE_VOLUME_C, _CACHE_FILE_C

    arquivo, volume = _carregar_params(db_path, "som_coberta", forcar_cache=True)

    if arquivo and Path(arquivo).exists():
        try:
            tmp = _gerar_wav_volume(arquivo, volume)
            _tocar_wav(tmp)
            _CACHE_PATH_C = arquivo
            _CACHE_VOLUME_C = volume
            _CACHE_FILE_C = tmp
            return
        except Exception as e:
            logger.warning("Falha ao testar coberta %s: %s", arquivo, e)

    import winsound

    winsound.Beep(800, 300)
