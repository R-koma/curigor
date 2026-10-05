import struct

from core.audio_signature import detect_audio_mime, wav_duration_seconds

_WEBM = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01"
_MP4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00"


def test_detects_webm_from_the_ebml_header() -> None:
    assert detect_audio_mime(_WEBM) == "audio/webm"


def test_detects_mp4_from_the_ftyp_box() -> None:
    assert detect_audio_mime(_MP4) == "audio/mp4"


def test_rejects_ogg() -> None:
    assert detect_audio_mime(b"OggS\x00\x02\x00\x00\x00\x00\x00\x00") is None


def test_rejects_bytes_too_short_for_a_signature() -> None:
    assert detect_audio_mime(b"\x00\x00\x00") is None


def test_rejects_empty_bytes() -> None:
    assert detect_audio_mime(b"") is None


def _wav(samples: int, *, rate: int = 16000, channels: int = 1, bits: int = 16, fmt: int = 1) -> bytes:
    data_size = samples * channels * bits // 8
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    header += b"fmt " + struct.pack(
        "<IHHIIHH", 16, fmt, channels, rate, rate * channels * bits // 8, channels * bits // 8, bits
    )
    header += b"data" + struct.pack("<I", data_size)
    return header + b"\x00" * data_size


def test_detects_wav_from_the_riff_header() -> None:
    assert detect_audio_mime(_wav(160)) == "audio/wav"


def test_wav_duration_is_derived_from_the_data_size() -> None:
    assert wav_duration_seconds(_wav(8000)) == 0.5


def test_wav_duration_rejects_stereo_and_non_pcm() -> None:
    assert wav_duration_seconds(_wav(160, channels=2)) is None
    assert wav_duration_seconds(_wav(160, fmt=3)) is None
    assert wav_duration_seconds(_wav(160, bits=8)) is None


def test_wav_duration_rejects_a_truncated_header() -> None:
    assert wav_duration_seconds(_wav(160)[:40]) is None


def test_wav_duration_rejects_sample_rates_other_than_16khz() -> None:
    assert wav_duration_seconds(_wav(160, rate=32000)) is None
    assert wav_duration_seconds(_wav(160, rate=44100)) is None


def test_wav_duration_rejects_a_header_only_wav() -> None:
    assert wav_duration_seconds(_wav(0)) is None
