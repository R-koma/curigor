import os

import freezegun
from hypothesis import settings

# freezegun が読み込み済みモジュールの属性を走査すると、langfuse.api の遅延 import が FakeDatetime の下で
# pydantic のモデルを作り、スキーマ生成に失敗する
freezegun.configure(extend_ignore_list=["langfuse"])

settings.register_profile("dev", max_examples=50)
settings.register_profile("ci", max_examples=200, deadline=None)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))
