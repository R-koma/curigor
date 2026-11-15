import { describe, expect, it } from "vitest";
import { HINT_GUIDE, HINT_TEXT } from "@/lib/hints";

describe("learning_side_question hint", () => {
  it("has both the banner text and the guide", () => {
    expect(HINT_TEXT.learning_side_question).toBe(
      "分からないことが出てきたら、文を選ぶか「横で質問」から聞けます。聞いたことはノートに残り、次の復習で確かめます。",
    );
    expect(HINT_GUIDE.learning_side_question).toMatchObject({
      title: "横で質問",
      body: "分からないことを、説明を止めずに聞けます。",
    });
  });
});
