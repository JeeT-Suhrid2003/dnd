"""Combat Service: the rules engine. Orchestrates Dice + Character services."""
import os
import re

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DICE_URL = os.getenv("DICE_URL", "http://localhost:8001")
CHARACTER_URL = os.getenv("CHARACTER_URL", "http://localhost:8002")

app = FastAPI(title="Combat Service", version="0.1.0")
DEFENDING: set[str] = set()


class InitiativeRequest(BaseModel):
    combatant_ids: list[str] = Field(min_length=1)


class AttackRequest(BaseModel):
    attacker_id: str
    target_id: str
    advantage: bool = False
    disadvantage: bool = False


class DefendRequest(BaseModel):
    character_id: str


async def call(method: str, base: str, path: str, **kwargs) -> dict:
    """Call a sibling service and translate failures into clean HTTP errors."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.request(method, f"{base}{path}", **kwargs)
    except httpx.RequestError as e:
        raise HTTPException(503, f"Upstream {base} unreachable: {type(e).__name__}")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.json().get("detail", r.text))
    return r.json()


def double_dice(notation: str) -> str:
    """Critical hits double the number of dice, not the modifier: 1d8+3 -> 2d8+3."""
    m = re.match(r"^\s*(\d*)d(\d+)(.*)$", notation, re.IGNORECASE)
    if not m:
        return notation
    count = int(m[1]) if m[1] else 1
    return f"{count * 2}d{m[2]}{m[3]}"


@app.get("/health")
def health():
    return {"service": "combat", "status": "ok"}


@app.post("/initiative")
async def roll_initiative(req: InitiativeRequest):
    DEFENDING.clear()
    entries = []
    for cid in req.combatant_ids:
        char = await call("GET", CHARACTER_URL, f"/characters/{cid}")
        dex_mod = char["modifiers"]["dexterity"]
        d20 = await call("POST", DICE_URL, "/d20", json={"modifier": dex_mod})
        entries.append({
            "id": char["id"], "name": char["name"],
            "initiative": d20["total"], "dex_mod": dex_mod, "roll": d20,
        })
    # Highest first; ties broken by higher Dexterity modifier
    entries.sort(key=lambda e: (e["initiative"], e["dex_mod"]), reverse=True)
    return {"order": entries}


@app.post("/defend")
async def defend(req: DefendRequest):
    character = await call("GET", CHARACTER_URL, f"/characters/{req.character_id}")
    if character["hp"] <= 0:
        raise HTTPException(409, f"{character['name']} is down and cannot defend")
    DEFENDING.add(character["id"])
    return {"character": character["name"], "bonus": 2}


@app.post("/attack")
async def attack(req: AttackRequest):
    attacker = await call("GET", CHARACTER_URL, f"/characters/{req.attacker_id}")
    target = await call("GET", CHARACTER_URL, f"/characters/{req.target_id}")

    if attacker["hp"] <= 0:
        raise HTTPException(409, f"{attacker['name']} is down and cannot attack")
    if target["hp"] <= 0:
        raise HTTPException(409, f"{target['name']} is already down")

    d20 = await call("POST", DICE_URL, "/d20", json={
        "modifier": attacker["attack_bonus"],
        "advantage": req.advantage, "disadvantage": req.disadvantage,
    })

    defense_used = target["id"] in DEFENDING
    if defense_used:
        DEFENDING.remove(target["id"])
    target_ac = target["ac"] + (2 if defense_used else 0)

    # Nat 20 always hits, nat 1 always misses, otherwise beat AC
    crit = d20["critical"] == "hit"
    hit = crit or (d20["critical"] != "fail" and d20["total"] >= target_ac)

    result = {
        "attacker": attacker["name"], "target": target["name"],
        "attack_roll": d20, "target_ac": target_ac, "defense_used": defense_used,
        "hit": hit, "critical": d20["critical"], "damage": None,
    }

    if hit:
        notation = double_dice(attacker["damage_dice"]) if crit else attacker["damage_dice"]
        dmg = await call("POST", DICE_URL, "/roll", json={"notation": notation})
        damage = max(0, dmg["total"])
        updated = await call("POST", CHARACTER_URL, f"/characters/{target['id']}/hp",
                             json={"delta": -damage})
        result["damage"] = {"roll": dmg, "amount": damage}
        result["target_hp"] = updated["hp"]
        result["target_down"] = updated["hp"] == 0
    else:
        result["target_hp"] = target["hp"]
        result["target_down"] = False

    result["summary"] = _summary(result)
    return result


def _summary(r: dict) -> str:
    roll = r["attack_roll"]["total"]
    if not r["hit"]:
        return f"{r['attacker']} attacks {r['target']} (rolled {roll} vs AC {r['target_ac']}) and misses."
    crit = " CRITICAL HIT!" if r["critical"] == "hit" else ""
    down = f" {r['target']} falls!" if r["target_down"] else ""
    return (f"{r['attacker']} hits {r['target']} (rolled {roll} vs AC {r['target_ac']}) "
            f"for {r['damage']['amount']} damage.{crit}{down}")
