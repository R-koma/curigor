from graph.state import DepthMapAspectState, DepthMapState

TRIAL_CORE_ASPECTS = 1
TRIAL_PURPOSE = "基本の仕組みを自分の言葉で説明できるようになる"


def limit_core_aspects(depth_map: DepthMapState, limit: int) -> DepthMapState:
    """先頭から `limit` 件だけ中核に残し、残りの中核は中核でない観点へ落とす。"""
    aspects: list[DepthMapAspectState] = []
    core_count = 0
    for aspect in depth_map["aspects"]:
        is_core = aspect["is_core"] and core_count < limit
        if is_core:
            core_count += 1
        aspects.append({**aspect, "is_core": is_core})
    return {"topic": depth_map["topic"], "aspects": aspects}


def trial_kickoff(topic: str) -> str:
    return (
        f"お試しの学習を始めましょう。「{topic}」について、知っていることを自分の言葉で説明してみてください。"
        "断片的でも大丈夫です。何回かやりとりしたら、画面上の「ノートを作成」でノートとフィードバックを作れます。"
    )
