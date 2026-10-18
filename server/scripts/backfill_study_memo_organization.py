"""要約も観点への振り分けも無い学習メモ（#731 より前に作ったもの）を整理し直す。

`uv run python -m scripts.backfill_study_memo_organization`
"""

import asyncio
import logging

from core.database import close_pool, get_pool
from graph.explore import build_overview, ordered_aspects
from graph.nodes._explore_llm import organize_memo
from repositories import study_memo_repository


async def main() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        targets = await study_memo_repository.find_unorganized(conn)
    organized = 0
    for memo in targets:
        aspects = ordered_aspects(memo["depth_map"])
        pairs = [(q["question"], q["answer"]) for q in memo["questions"]]
        organization = await organize_memo(memo["topic"], aspects, pairs, memo["glossary"])
        if organization is None:
            continue
        overview = build_overview(aspects, organization, question_count=len(pairs), term_count=len(memo["glossary"]))
        async with pool.acquire() as conn:
            await study_memo_repository.update(
                conn,
                memo["id"],
                memo["user_id"],
                {"summary": organization.summary.strip(), "overview": overview},
            )
        organized += 1
    await close_pool()
    print(f"organized {organized}/{len(targets)} study memos")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
