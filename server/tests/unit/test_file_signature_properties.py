import struct

from hypothesis import given
from hypothesis import strategies as st

from core.audio_signature import detect_audio_mime, wav_duration_seconds
from core.image_signature import detect_image_mime


@given(data=st.binary())
def test_detect_image_mime_returns_supported_mime_or_none(data: bytes) -> None:
    assert detect_image_mime(data) in {"image/png", "image/jpeg", "image/webp", None}


@given(data=st.binary())
def test_detect_audio_mime_returns_supported_mime_or_none(data: bytes) -> None:
    assert detect_audio_mime(data) in {"audio/webm", "audio/mp4", "audio/wav", None}


@given(data=st.binary())
def test_wav_duration_is_none_or_non_negative(data: bytes) -> None:
    duration = wav_duration_seconds(data)
    assert duration is None or duration >= 0


@given(header=st.binary(min_size=44, max_size=44), payload=st.binary(min_size=1))
def test_wav_duration_never_raises_on_header_shaped_bytes(header: bytes, payload: bytes) -> None:
    data = bytearray(header)
    data[12:16] = b"fmt "
    data[36:40] = b"data"
    wav_duration_seconds(bytes(data) + payload)


@given(payload=st.binary(min_size=1, max_size=4096))
def test_wav_duration_of_standard_header_is_payload_length_over_byte_rate(payload: bytes) -> None:
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(payload))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
        + b"data"
        + struct.pack("<I", len(payload))
    )
    data = header + payload

    assert detect_audio_mime(data) == "audio/wav"
    assert wav_duration_seconds(data) == len(payload) / 32000
