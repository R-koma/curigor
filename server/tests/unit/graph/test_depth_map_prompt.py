from graph.prompts.depth_map import build_depth_map_prompt


class TestBuildDepthMapPrompt:
    def test_interpolates_topic_and_known_fields(self) -> None:
        rendered = build_depth_map_prompt(
            topic="システムコール",
            purpose="strace で調査できるようになりたい",
            source="Linuxのしくみ",
            prior_knowledge="OSの授業を受けた",
        )
        assert "システムコール" in rendered
        assert "strace で調査できるようになりたい" in rendered
        assert "Linuxのしくみ" in rendered
        assert "OSの授業を受けた" in rendered

    def test_unspecified_fields_use_placeholder(self) -> None:
        rendered = build_depth_map_prompt(topic="キュー", purpose="", source="", prior_knowledge="")
        assert "未指定" in rendered

    def test_warns_against_shallow_example_only_reasoning(self) -> None:
        rendered = build_depth_map_prompt(topic="キュー", purpose="", source="", prior_knowledge="")
        assert "日常の具体例を挙げさせるだけの問いにしない" in rendered

    def test_reasoned_question_does_not_name_a_contrast_the_learner_may_not_know(self) -> None:
        rendered = build_depth_map_prompt(topic="キュー", purpose="", source="", prior_knowledge="")
        assert "なぜ〇〇ではなく△△" not in rendered
        assert "比べる相手（「なぜ△△ではなく〇〇か」の△△）を名指ししない" in rendered
