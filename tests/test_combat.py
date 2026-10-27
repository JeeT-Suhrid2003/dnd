import importlib.util
import pathlib
import sys

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "combat_service_main", ROOT / "services" / "combat" / "main.py"
)
combat = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = combat
SPEC.loader.exec_module(combat)


def test_defend_adds_two_ac_until_next_attack(monkeypatch):
    combatant_data = {
        "player": {"id": "player", "name": "Hero", "hp": 10, "attack_bonus": 2, "damage_dice": "1d6"},
        "target": {"id": "target", "name": "Guard", "hp": 10, "ac": 12},
    }

    async def fake_call(method, base, path, **kwargs):
        if method == "GET":
            return dict(combatant_data[path.rsplit("/", 1)[-1]])
        if path == "/d20":
            return {"total": 13, "critical": None, "rolls": [13], "mode": "normal"}
        if path == "/roll":
            return {"total": 2, "rolls": [2]}
        if path.endswith("/hp"):
            target = combatant_data["target"]
            target["hp"] += kwargs["json"]["delta"]
            return dict(target)
        raise AssertionError(f"Unexpected upstream request: {method} {path}")

    monkeypatch.setattr(combat, "call", fake_call)
    combat.DEFENDING.clear()
    client = TestClient(combat.app)

    defended = client.post("/defend", json={"character_id": "target"})
    assert defended.status_code == 200
    assert defended.json()["bonus"] == 2

    first_attack = client.post("/attack", json={"attacker_id": "player", "target_id": "target"})
    assert first_attack.status_code == 200
    assert first_attack.json()["target_ac"] == 14
    assert first_attack.json()["defense_used"] is True
    assert first_attack.json()["hit"] is False

    next_attack = client.post("/attack", json={"attacker_id": "player", "target_id": "target"})
    assert next_attack.status_code == 200
    assert next_attack.json()["target_ac"] == 12
    assert next_attack.json()["defense_used"] is False
    assert next_attack.json()["hit"] is True
    assert next_attack.json()["target_hp"] == 8
    combat.DEFENDING.clear()
