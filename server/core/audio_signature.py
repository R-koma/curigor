_EBML_SIGNATURE = b"\x1a\x45\xdf\xa3"


def detect_audio_mime(data: bytes) -> str | None:
    if data.startswith(_EBML_SIGNATURE):
        return "audio/webm"
    # MP4 は ISO BMFF: <4byte size>"ftyp"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "audio/mp4"
    return None
