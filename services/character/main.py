"""Character Service: owns character and monster sheets (in-memory for now)."""
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Character Service", version="0.1.0")


class Abilities(BaseModel):
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10


class CharacterIn(BaseModel):
    name: str
    kind: Literal["player", "monster"] = "player"
    char_class: str = "Fighter"
    level: int = Field(default=1, ge=1, le=20)
    abilities: Abilities = Abilities()
    max_hp: int = Field(default=10, ge=1)
    ac: int = Field(default=10, ge=1)
    attack_bonus: int = 0
    damage_dice: str = "1d6"


class HpChange(BaseModel):
    delta: int = Field(description="Negative = damage, positive = healing")


DB: dict[str, dict] = {}


def modifier(score: int) -> int:
    return (score - 10) // 2


def _build(data: CharacterIn, char_id: str | None = None) -> dict:
    c = data.model_dump()
    c["id"] = char_id or uuid.uuid4().hex[:8]
    c["hp"] = c["max_hp"]
    c["modifiers"] = {k: modifier(v) for k, v in c["abilities"].items()}
    return c


def _seed():
    DB.clear()
    for cid, data in {
        "aria": CharacterIn(
            name="Aria Stormblade", char_class="Fighter", level=1,
            abilities=Abilities(strength=16, dexterity=14, constitution=14, intelligence=10, wisdom=12, charisma=8),
            max_hp=13, ac=16, attack_bonus=5, damage_dice="1d8+3",
        ),
        "goblin": CharacterIn(
            name="Goblin", kind="monster", char_class="Goblin",
            abilities=Abilities(strength=8, dexterity=14, constitution=10, intelligence=10, wisdom=8, charisma=8),
            max_hp=7, ac=15, attack_bonus=4, damage_dice="1d6+2",
        ),
    }.items():
        DB[cid] = _build(data, cid)


_seed()


@app.get("/health")
def health():
    return {"service": "character", "status": "ok", "count": len(DB)}


@app.get("/characters")
def list_characters():
    return list(DB.values())


@app.post("/characters", status_code=201)
def create_character(data: CharacterIn):
    c = _build(data)
    DB[c["id"]] = c
    return c


@app.get("/characters/{char_id}")
def get_character(char_id: str):
    if char_id not in DB:
        raise HTTPException(404, f"Character {char_id!r} not found")
    return DB[char_id]


@app.post("/characters/{char_id}/hp")
def change_hp(char_id: str, change: HpChange):
    c = get_character(char_id)
    c["hp"] = max(0, min(c["max_hp"], c["hp"] + change.delta))
    return c


@app.post("/characters/{char_id}/reset")
def reset_hp(char_id: str):
    c = get_character(char_id)
    c["hp"] = c["max_hp"]
    return c


@app.delete("/characters/{char_id}", status_code=204)
def delete_character(char_id: str):
    get_character(char_id)
    del DB[char_id]
