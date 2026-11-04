"""Reglas oficiales adoptadas para el laboratorio, sin dependencias externas."""
from datetime import timedelta


def outcome(home: int, away: int) -> int:
    return (home > away) - (home < away)


def score_prediction(pred_home, pred_away, real_home, real_away, created_at, kickoff, streak_before=0):
    """Devuelve desglose de puntos y racha posterior.

    Prioridad: exacto=5 (sin apilar); si no, ganador=3 y margen=2
    acumulables cuando aplican. Racha +2 por cada tercer acierto
    consecutivo del resultado 1X2. Anticipación >24 h = +1.
    """
    correct_winner = outcome(pred_home, pred_away) == outcome(real_home, real_away)
    exact = pred_home == real_home and pred_away == real_away
    if exact:
        base, difference = 5, 0
    else:
        base = 3 if correct_winner else 0
        # Diferencia de goles solo con el mismo signo y victoria (no empate).
        difference = 2 if (correct_winner and outcome(real_home, real_away) != 0 and
                           pred_home - pred_away == real_home - real_away) else 0
    streak = streak_before + 1 if correct_winner else 0
    streak_bonus = 2 if correct_winner and streak % 3 == 0 else 0
    anticipation = 1 if kickoff - created_at > timedelta(hours=24) else 0
    return {
        "base": base,
        "difference": difference,
        "streak_bonus": streak_bonus,
        "anticipation": anticipation,
        "total": base + difference + streak_bonus + anticipation,
        "correct_winner": correct_winner,
        "streak": streak,
        "exact": exact,
    }


def compute_scoreboard(matches, predictions):
    """Solo partidos finalizados; partido no pronosticado rompe racha.

    Los partidos se ordenan cronológicamente para evitar puntajes dependientes
    del orden en que el administrador registre los resultados.
    """
    by_match = {p.match_id: p for p in predictions}
    result = {"total": 0, "correct": 0, "details": {}, "streak": 0}
    completed = sorted(
        (m for m in matches if m.home_score is not None and m.away_score is not None),
        key=lambda m: (m.kickoff, m.id),
    )
    for match in completed:
        pred = by_match.get(match.id)
        if pred is None:
            result["streak"] = 0
            continue
        detail = score_prediction(pred.home_goals, pred.away_goals, match.home_score,
                                  match.away_score, pred.created_at, match.kickoff, result["streak"])
        result["total"] += detail["total"]
        result["correct"] += int(detail["correct_winner"])
        result["streak"] = detail["streak"]
        result["details"][match.id] = detail
    return result
