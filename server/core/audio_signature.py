import struct

_EBML_SIGNATURE = b"\x1a\x45\xdf\xa3"
_WAV_HEADER_BYTES = 44
_WAV_SAMPLE_RATE = 16000


def detect_audio_mime(data: bytes) -> str | None:
    if data.startswith(_EBML_SIGNATURE):
        return "audio/webm"
    # MP4 は ISO BMFF: <4byte size>"ftyp"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "audio/mp4"
    # WAV は RIFF コンテナ: "RIFF"<4byte size>"WAVE"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    return None


def wav_duration_seconds(data: bytes) -> float | None:
    # クライアントが書く 44 バイトの標準ヘッダー（fmt → data の順・PCM 16bit モノラル）だけを受け付ける
    if len(data) <= _WAV_HEADER_BYTES or data[12:16] != b"fmt " or data[36:40] != b"data":
        return None
    audio_format, channels, sample_rate = struct.unpack_from("<HHI", data, 20)
    (bits,) = struct.unpack_from("<H", data, 34)
    if audio_format != 1 or channels != 1 or bits != 16 or sample_rate != _WAV_SAMPLE_RATE:
        return None
    return float((len(data) - _WAV_HEADER_BYTES) / (sample_rate * 2))
