import importlib.util
import os
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "character_service_main", ROOT / "services" / "character" / "main.py"
)
character = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = character
SPEC.loader.exec_module(character)


@pytest.fixture
def database_url(monkeypatch):
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    monkeypatch.setenv("DATABASE_URL", test_url)
    character.initialize_db()
    with character._connect() as connection:
        connection.execute("TRUNCATE characters RESTART IDENTITY")
        connection.execute("DELETE FROM app_metadata")
    return test_url


def test_character_endpoints_use_persistent_database(database_url):
    with TestClient(character.app) as client:
        seeded = client.get("/characters").json()
        assert [item["id"] for item in seeded] == ["aria", "goblin"]

        created = client.post(
            "/characters",
            json={
                "name": "Mira Quickstep",
                "abilities": {"dexterity": 16},
                "max_hp": 12,
            },
        )
        assert created.status_code == 201
        character_id = created.json()["id"]
        assert created.json()["hp"] == 12

        damaged = client.post(
            f"/characters/{character_id}/hp", json={"delta": -5}
        )
        assert damaged.json()["hp"] == 7
        assert damaged.json()["modifiers"]["dexterity"] == 3

    with TestClient(character.app) as client:
        assert client.get(f"/characters/{character_id}").json()["hp"] == 7
        assert client.get("/health").json()["count"] == 3
        assert client.post(f"/characters/{character_id}/reset").json()["hp"] == 12
        assert client.post(
            f"/characters/{character_id}/hp", json={"delta": 100}
        ).json()["hp"] == 12
        assert client.delete(f"/characters/{character_id}").status_code == 204
        assert client.get(f"/characters/{character_id}").status_code == 404


def test_deleted_seed_is_not_restored_on_restart(database_url):
    with TestClient(character.app) as client:
        assert client.delete("/characters/aria").status_code == 204

    with TestClient(character.app) as client:
        assert client.get("/characters/aria").status_code == 404
