"""Kural motoru — Step 0."""

from agent.fakes import make_geo
from agent.risk.registry import RULES
from agent.risk.scoring import level_for, score


def test_level_boundaries():
    assert [level_for(x) for x in (0, 25, 50, 90)] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def test_rules_are_discovered():
    assert {"proximity.near_base", "motion.approaching_base", "reports.confirmed_threat_report"} <= set(RULES)


def test_score_equals_sum_of_factors():
    f = score(make_geo(), None, None, [])
    assert f.score == sum(x.points for x in f.factors)
