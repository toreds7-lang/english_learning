"""Leitner-box spaced repetition.

box 0      new (never studied)
box 1-3    learning
box 4-5    mastered (still checked at long intervals)

A correct answer moves a word up one box and schedules it further out;
a wrong answer sends it back to box 1 for tomorrow.
"""
from __future__ import annotations

from datetime import date, timedelta

INTERVAL_DAYS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
MASTERED_BOX = 4
MAX_BOX = 5


def status(box: int) -> str:
    if box <= 0:
        return "new"
    return "mastered" if box >= MASTERED_BOX else "learning"


def after_answer(box: int, correct: bool, today: date) -> tuple[int, date]:
    if correct:
        new_box = min(max(box, 0) + 1, MAX_BOX)
        return new_box, today + timedelta(days=INTERVAL_DAYS[new_box])
    return 1, today + timedelta(days=1)


def mark_known(today: date) -> tuple[int, date]:
    """Student already knows the word (pretest or "I know it"): skip ahead, check in 2 weeks."""
    return MASTERED_BOX, today + timedelta(days=INTERVAL_DAYS[MASTERED_BOX])


def mark_learning(box: int, today: date) -> tuple[int, date]:
    """Student wants to learn the word: put it in today's review."""
    return (box if 1 <= box < MASTERED_BOX else 1), today
