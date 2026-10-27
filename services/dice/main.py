"""Dice Service: rolls dice. Knows nothing about characters or combat."""
import random

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from dice import DiceError, roll, roll_d20

app = FastAPI(title="Dice Service", version="0.1.0")


class RollRequest(BaseModel):
    notation: str = Field(examples=["2d6+3", "d20", "4d6kh3"])
    seed: int | None = Field(default=None, description="Optional seed for reproducible rolls")


class D20Request(BaseModel):
    modifier: int = 0
    advantage: bool = False
    disadvantage: bool = False
    seed: int | None = None


def _rng(seed: int | None) -> random.Random | None:
    return random.Random(seed) if seed is not None else None


@app.get("/health")
def health():
    return {"service": "dice", "status": "ok"}


@app.post("/roll")
def roll_dice(req: RollRequest):
    try:
        return roll(req.notation, _rng(req.seed)).to_dict()
    except DiceError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/roll/{notation}")
def roll_dice_get(notation: str):
    """Convenience: GET /roll/2d6+3 (encode + as %2B in browsers)."""
    try:
        return roll(notation.replace(" ", "+")).to_dict()
    except DiceError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/d20")
def roll_d20_endpoint(req: D20Request):
    return roll_d20(req.modifier, req.advantage, req.disadvantage, _rng(req.seed)).to_dict()
