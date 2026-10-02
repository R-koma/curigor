from core.audio_signature import detect_audio_mime

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
