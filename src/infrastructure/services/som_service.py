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


def _carregar_params(db_path):
    from src.infrastructure.persistence.repositories.repositories import ParametroRepository

    repo = ParametroRepository(db_path)
    arquivo_p = repo.get_by_chave("som_arquivo")
    volume_p = repo.get_by_chave("som_volume")

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

    def _on_state(state):
        if state == QMediaPlayer.StoppedState:
            loop.quit()

    player.mediaStatusChanged.connect(
        lambda s: loop.quit() if s == QMediaPlayer.EndOfMedia else None
    )
    player.errorOccurred.connect(lambda e: loop.quit())

    QTimer.singleShot(10000, loop.quit)

    player.play()
    loop.exec_()


def tocar(db_path=None):
    global _CACHE_PATH, _CACHE_VOLUME, _CACHE_DB_PATH, _CACHE_FILE

    arquivo, volume = _carregar_params(db_path) if db_path else ("", 1.0)

    if arquivo and Path(arquivo).exists():
        if _CACHE_PATH == arquivo and _CACHE_VOLUME == volume and _CACHE_DB_PATH == db_path and _CACHE_FILE:
            try:
                _tocar_wav(_CACHE_FILE)
            except Exception:
                pass
            return

        try:
            tmp = _gerar_wav_volume(arquivo, volume)
            _tocar_wav(tmp)
            _CACHE_PATH = arquivo
            _CACHE_VOLUME = volume
            _CACHE_DB_PATH = db_path
            _CACHE_FILE = tmp
            return
        except Exception as e:
            logger.warning("Falha ao tocar %s: %s. Usando beep.", arquivo, e)

    import winsound

    winsound.Beep(1000, 200)
    winsound.Beep(1200, 150)


def testar(db_path):
    global _CACHE_PATH, _CACHE_VOLUME, _CACHE_FILE

    arquivo, volume = _carregar_params(db_path)

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