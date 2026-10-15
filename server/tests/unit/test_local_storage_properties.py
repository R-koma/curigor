from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from storage.local import LocalObjectStorage

segments = st.one_of(
    st.sampled_from(["..", ".", "", "a", "\x00", "~", "\\..", "..\\"]),
    st.text(max_size=20),
)
keys = st.one_of(
    st.text(),
    st.builds(
        lambda prefix, parts: prefix + "/".join(parts),
        st.sampled_from(["", "/", "//", "../"]),
        st.lists(segments, max_size=8),
    ),
)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(key=keys)
def test_resolve_rejects_or_stays_inside_base_dir(tmp_path: Path, key: str) -> None:
    storage = LocalObjectStorage(tmp_path)
    base = tmp_path.resolve()
    try:
        resolved = storage._resolve(key)
    except ValueError:
        return
    assert resolved == base or base in resolved.parents


@pytest.mark.parametrize("key", ["/etc/passwd", "a/\x00/b", "../" * 10 + "etc"])
def test_resolve_rejects_known_escapes(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError):
        LocalObjectStorage(tmp_path)._resolve(key)
