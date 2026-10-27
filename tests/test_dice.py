import pathlib
import random
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "services" / "dice"))

from fastapi.testclient import TestClient  # noqa: E402

from dice import DiceError, roll, roll_d20  # noqa: E402
from main import app  # noqa: E402


def test_basic_roll_in_range():
    for _ in range(200):
        r = roll("2d6+3")
        assert len(r.rolls) == 2
        assert all(1 <= x <= 6 for x in r.rolls)
        assert r.total == sum(r.rolls) + 3


def test_implicit_count_and_negative_modifier():
    r = roll("d20-1")
    assert len(r.rolls) == 1
    assert r.total == r.rolls[0] - 1


def test_keep_highest():
    r = roll("4d6kh3", random.Random(1))
    assert len(r.rolls) == 4 and len(r.kept) == 3
    assert r.total == sum(sorted(r.rolls, reverse=True)[:3])


def test_keep_lowest():
    r = roll("4d6kl1", random.Random(2))
    assert r.kept == [min(r.rolls)]


def test_seed_is_reproducible():
    assert roll("10d10", random.Random(42)).rolls == roll("10d10", random.Random(42)).rolls


@pytest.mark.parametrize("bad", ["", "abc", "2d", "0d6", "101d6", "1d1", "1d1001", "3d6kh4", "2d6++1"])
def test_invalid_notation(bad):
    with pytest.raises(DiceError):
        roll(bad)


def test_crit_detection():
    seen = set()
    for seed in range(500):
        r = roll("d20", random.Random(seed))
        if r.natural == 20:
            assert r.critical == "hit"
        elif r.natural == 1:
            assert r.critical == "fail"
        else:
            assert r.critical is None
        seen.add(r.critical)
    assert {"hit", "fail", None} <= seen


def test_advantage_takes_higher_and_disadvantage_lower():
    adv = roll_d20(advantage=True, rng=random.Random(7))
    dis = roll_d20(disadvantage=True, rng=random.Random(7))
    assert adv.detail["mode"] == "advantage" and adv.kept == [max(adv.rolls)]
    assert dis.detail["mode"] == "disadvantage" and dis.kept == [min(dis.rolls)]


def test_advantage_and_disadvantage_cancel():
    r = roll_d20(advantage=True, disadvantage=True)
    assert r.detail["mode"] == "normal" and len(r.rolls) == 1


def test_http_endpoints():
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"

    r = c.post("/roll", json={"notation": "2d6+3", "seed": 5})
    assert r.status_code == 200
    assert r.json() == c.post("/roll", json={"notation": "2d6+3", "seed": 5}).json()

    assert c.post("/roll", json={"notation": "nope"}).status_code == 422

    d = c.post("/d20", json={"modifier": 5, "advantage": True}).json()
    assert d["mode"] == "advantage" and d["modifier"] == 5
