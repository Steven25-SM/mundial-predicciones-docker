from datetime import datetime, timedelta
from dataclasses import dataclass
from scoring import score_prediction, compute_scoreboard

kickoff = datetime(2026, 12, 1, 20, 0)
early = kickoff - timedelta(hours=25)
late = kickoff - timedelta(minutes=10)


def test_exact_result_and_early_bonus():
    s = score_prediction(2, 1, 2, 1, early, kickoff)
    assert s["base"] == 5 and s["difference"] == 0
    assert s["anticipation"] == 1 and s["total"] == 6


def test_correct_winner_only():
    s = score_prediction(1, 0, 3, 1, late, kickoff)
    assert s["base"] == 3 and s["difference"] == 0 and s["total"] == 3


def test_correct_margin_adds_two():
    s = score_prediction(3, 1, 2, 0, late, kickoff)
    assert s["base"] == 3 and s["difference"] == 2 and s["total"] == 5


def test_draw_correct_without_exact_score():
    s = score_prediction(2, 2, 0, 0, late, kickoff)
    assert s["base"] == 3 and s["difference"] == 0


def test_wrong_prediction_is_zero_last_minute():
    assert score_prediction(0, 2, 2, 0, late, kickoff)["total"] == 0


def test_early_strictly_more_than_24_hours():
    s = score_prediction(0, 2, 2, 0, kickoff - timedelta(hours=24), kickoff)
    assert s["anticipation"] == 0
    s = score_prediction(0, 2, 2, 0, kickoff - timedelta(hours=24, seconds=1), kickoff)
    assert s["anticipation"] == 1


def test_third_straight_correct_gets_two_points():
    first = score_prediction(1, 0, 2, 0, late, kickoff, 0)
    second = score_prediction(1, 0, 2, 0, late, kickoff, first["streak"])
    third = score_prediction(1, 0, 2, 0, late, kickoff, second["streak"])
    assert first["streak_bonus"] == second["streak_bonus"] == 0
    assert third["streak_bonus"] == 2


@dataclass
class Match:
    id: int
    kickoff: datetime
    home_score: int | None
    away_score: int | None


@dataclass
class Prediction:
    match_id: int
    home_goals: int
    away_goals: int
    created_at: datetime


def test_unpredicted_match_resets_streak():
    matches = [Match(1, kickoff, 2, 0), Match(2, kickoff + timedelta(days=1), 2, 0),
               Match(3, kickoff + timedelta(days=2), 2, 0)]
    preds = [Prediction(1, 1, 0, late), Prediction(3, 1, 0, kickoff + timedelta(days=2, minutes=-10))]
    out = compute_scoreboard(matches, preds)
    assert out["total"] == 6 and out["streak"] == 1


def test_unfinished_match_does_not_count():
    matches = [Match(1, kickoff, None, None)]
    preds = [Prediction(1, 2, 0, early)]
    assert compute_scoreboard(matches, preds)["total"] == 0
