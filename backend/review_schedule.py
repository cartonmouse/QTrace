from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping


def _quality_from_score(score_0_10: float) -> int:
    """Map the product's 0-10 review score to the SM-2 quality scale (0-5)."""
    score = max(0.0, min(10.0, float(score_0_10)))
    if score <= 2:
        return 0
    if score <= 4:
        return 2
    if score <= 5:
        return 3
    if score <= 7:
        return 4
    return 5


def initial_schedule(today: date | None = None) -> dict[str, Any]:
    """Create a due-now item when a weak point is first discovered."""
    review_date = today or date.today()
    return {
        "interval_days": 1,
        "ease_factor": 2.5,
        "repetitions": 0,
        "next_review": review_date.isoformat(),
        "last_score": None,
    }


def sm2_update(
    current: Mapping[str, Any] | None,
    score_0_10: float,
    today: date | None = None,
) -> dict[str, Any]:
    """Advance one review item using a small, explainable SM-2 variant.

    A score below 6/10 is treated as a failed recall. Failed recall resets the
    repetition count and brings the item back tomorrow. Successful recalls use
    the familiar 1 day -> 3 days -> ease-factor growth sequence.
    """
    current = current or {}
    quality = _quality_from_score(score_0_10)
    ease_factor = float(current.get("ease_factor", 2.5) or 2.5)
    repetitions = int(current.get("repetitions", 0) or 0)
    interval_days = int(current.get("interval_days", 1) or 1)

    if quality < 3:
        repetitions = 0
        interval_days = 1
    elif repetitions == 0:
        repetitions = 1
        interval_days = 1
    elif repetitions == 1:
        repetitions = 2
        interval_days = 3
    else:
        repetitions += 1
        interval_days = max(1, int(interval_days * ease_factor))

    ease_factor = max(
        1.3,
        ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02),
    )
    review_date = today or date.today()
    return {
        "interval_days": interval_days,
        "ease_factor": round(ease_factor, 3),
        "repetitions": repetitions,
        "next_review": (review_date + timedelta(days=interval_days)).isoformat(),
        "last_score": max(0.0, min(10.0, float(score_0_10))),
    }


def is_due(next_review: str, today: date | None = None) -> bool:
    return next_review <= (today or date.today()).isoformat()
