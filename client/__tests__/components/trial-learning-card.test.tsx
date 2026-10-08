import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TrialLearningCard } from "@/components/dashboard/trial-learning-card";
import { findTrialTopic, TRIAL_TOPICS } from "@/lib/trial";

describe("TrialLearningCard", () => {
  it("links each trial topic to a trial learning session", () => {
    render(<TrialLearningCard />);

    expect(
      screen.getByRole("heading", { name: "お試しで学習する" }),
    ).toBeInTheDocument();
    for (const { id, topic } of TRIAL_TOPICS) {
      expect(screen.getByRole("link", { name: topic })).toHaveAttribute(
        "href",
        `/learn?trial=${id}`,
      );
    }
  });
});

describe("findTrialTopic", () => {
  it("returns null for an unknown or missing id", () => {
    expect(findTrialTopic("unknown")).toBeNull();
    expect(findTrialTopic(null)).toBeNull();
    expect(findTrialTopic(TRIAL_TOPICS[0].id)).toBe(TRIAL_TOPICS[0]);
  });
});
