"""学習系対話ノード（legacy / 聞き取り / 地図駆動）で共有する小さなヘルパー。"""

from graph.state import LearningState


def recent_messages_block(state: LearningState, limit: int = 6) -> str:
    return "\n".join(
        f"{'ユーザー' if msg.type == 'human' else 'AI'}: {msg.content}" for msg in state["messages"][-limit:]
    )
