"""Character Service: owns character and monster sheets."""
import os
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Iterator, Literal

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_db()
    yield


app = FastAPI(title="Character Service", version="0.1.0", lifespan=lifespan)


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


def modifier(score: int) -> int:
    return (score - 10) // 2


def _build(data: CharacterIn, char_id: str | None = None, hp: int | None = None) -> dict:
    c = data.model_dump()
    c["id"] = char_id or uuid.uuid4().hex[:8]
    c["hp"] = c["max_hp"] if hp is None else hp
    c["modifiers"] = {k: modifier(v) for k, v in c["abilities"].items()}
    return c


@contextmanager
def _connect() -> Iterator[psycopg.Connection]:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        connection = psycopg.connect(
            database_url, connect_timeout=5, row_factory=dict_row
        )
    else:
        connection = psycopg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            dbname=os.getenv("DB_NAME", "dnd"),
            user=os.getenv("DB_USER", "dnd"),
            password=os.getenv("DB_PASSWORD", "dnd-dev-password"),
            connect_timeout=5,
            row_factory=dict_row,
        )
    with connection:
        yield connection


def _save_character(connection: sqlite3.Connection, character: dict) -> None:
    connection.execute(
        """
        INSERT INTO characters (
            id, name, kind, char_class, level, abilities, max_hp, hp, ac,
            attack_bonus, damage_dice
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            character["id"], character["name"], character["kind"],
            character["char_class"], character["level"],
            Jsonb(character["abilities"]), character["max_hp"],
            character["hp"], character["ac"], character["attack_bonus"],
            character["damage_dice"],
        ),
    )


def _from_row(row: dict) -> dict:
    return _build(
        CharacterIn(
            name=row["name"],
            kind=row["kind"],
            char_class=row["char_class"],
            level=row["level"],
            abilities=Abilities(**row["abilities"]),
            max_hp=row["max_hp"],
            ac=row["ac"],
            attack_bonus=row["attack_bonus"],
            damage_dice=row["damage_dice"],
        ),
        char_id=row["id"],
        hp=row["hp"],
    )


def initialize_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                created_order BIGSERIAL UNIQUE NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                char_class TEXT NOT NULL,
                level INTEGER NOT NULL,
                abilities JSONB NOT NULL,
                max_hp INTEGER NOT NULL,
                hp INTEGER NOT NULL,
                ac INTEGER NOT NULL,
                attack_bonus INTEGER NOT NULL,
                damage_dice TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        seeded = connection.execute(
            """
            INSERT INTO app_metadata (key, value)
            VALUES ('default_characters_seeded', 'true')
            ON CONFLICT (key) DO NOTHING
            RETURNING key
            """
        ).fetchone()
        if seeded:
            for cid, data in {
                "aria": CharacterIn(
                    name="Aria Stormblade", char_class="Fighter", level=1,
                    abilities=Abilities(
                        strength=16, dexterity=14, constitution=14,
                        intelligence=10, wisdom=12, charisma=8,
                    ),
                    max_hp=13, ac=16, attack_bonus=5, damage_dice="1d8+3",
                ),
                "goblin": CharacterIn(
                    name="Goblin", kind="monster", char_class="Goblin",
                    abilities=Abilities(
                        strength=8, dexterity=14, constitution=10,
                        intelligence=10, wisdom=8, charisma=8,
                    ),
                    max_hp=7, ac=15, attack_bonus=4, damage_dice="1d6+2",
                ),
            }.items():
                _save_character(connection, _build(data, cid))


@app.get("/health")
def health():
    with _connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM characters"
        ).fetchone()["count"]
    return {"service": "character", "status": "ok", "count": count}


@app.get("/characters")
def list_characters():
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM characters ORDER BY created_order"
        ).fetchall()
    return [_from_row(row) for row in rows]


@app.post("/characters", status_code=201)
def create_character(data: CharacterIn):
    c = _build(data)
    with _connect() as connection:
        _save_character(connection, c)
    return c


@app.get("/characters/{char_id}")
def get_character(char_id: str):
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM characters WHERE id = %s", (char_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, f"Character {char_id!r} not found")
    return _from_row(row)


@app.post("/characters/{char_id}/hp")
def change_hp(char_id: str, change: HpChange):
    with _connect() as connection:
        row = connection.execute(
            """
            UPDATE characters
            SET hp = GREATEST(0, LEAST(max_hp, hp + %s))
            WHERE id = %s
            RETURNING *
            """,
            (change.delta, char_id),
        ).fetchone()
    if row is None:
        raise HTTPException(404, f"Character {char_id!r} not found")
    return _from_row(row)


@app.post("/characters/{char_id}/reset")
def reset_hp(char_id: str):
    with _connect() as connection:
        row = connection.execute(
            "UPDATE characters SET hp = max_hp WHERE id = %s RETURNING *",
            (char_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, f"Character {char_id!r} not found")
    return _from_row(row)


@app.delete("/characters/{char_id}", status_code=204)
def delete_character(char_id: str):
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM characters WHERE id = %s", (char_id,)
        )
    if cursor.rowcount == 0:
        raise HTTPException(404, f"Character {char_id!r} not found")
