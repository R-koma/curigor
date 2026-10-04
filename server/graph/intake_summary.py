from collections.abc import Mapping
from typing import Any

from schemas.websocket_message import IntakeSummary


def build_intake_summary(values: Mapping[str, Any]) -> IntakeSummary | None:
    summary = IntakeSummary(
        purpose=(values.get("learning_goal") or "").strip(),
        source=(values.get("learning_source") or "").strip(),
        prior_knowledge=(values.get("prior_knowledge") or "").strip(),
    )
    return summary if summary.purpose or summary.source or summary.prior_knowledge else None
