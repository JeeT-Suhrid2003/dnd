"""Pure dice-rolling logic. No HTTP in here, so it is trivial to unit test."""
import random
import re
from dataclasses import dataclass, field

MAX_DICE = 100
MAX_SIDES = 1000

# NdM, optional keep-highest/lowest (kh/kl), optional +/- modifier
# Examples: d20, 2d6+3, 4d6kh3, 1d20-1
NOTATION = re.compile(
    r"^\s*(?P<count>\d*)d(?P<sides>\d+)"
    r"(?:(?P<keep>kh|kl)(?P<keep_n>\d+))?"
    r"(?P<mod>[+-]\d+)?\s*$",
    re.IGNORECASE,
)


class DiceError(ValueError):
    """Raised for invalid dice notation or out-of-range values."""


@dataclass
class RollResult:
    notation: str
    rolls: list[int]
    kept: list[int]
    modifier: int
    total: int
    natural: int | None = None  # kept d20 value, for crit detection
    critical: str | None = None  # "hit" (nat 20), "fail" (nat 1) or None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "notation": self.notation,
            "rolls": self.rolls,
            "kept": self.kept,
            "modifier": self.modifier,
            "total": self.total,
            "natural": self.natural,
            "critical": self.critical,
            **self.detail,
        }


def roll(notation: str, rng: random.Random | None = None) -> RollResult:
    rng = rng or random
    m = NOTATION.match(notation)
    if not m:
        raise DiceError(f"Invalid dice notation: {notation!r} (try 2d6+3, d20, 4d6kh3)")

    count = int(m["count"]) if m["count"] else 1
    sides = int(m["sides"])
    modifier = int(m["mod"]) if m["mod"] else 0

    if not 1 <= count <= MAX_DICE:
        raise DiceError(f"Dice count must be between 1 and {MAX_DICE}")
    if not 2 <= sides <= MAX_SIDES:
        raise DiceError(f"Dice sides must be between 2 and {MAX_SIDES}")

    rolls = [rng.randint(1, sides) for _ in range(count)]
    kept = list(rolls)

    if m["keep"]:
        keep_n = int(m["keep_n"])
        if not 1 <= keep_n <= count:
            raise DiceError("Keep count must be between 1 and the number of dice")
        kept = sorted(rolls, reverse=m["keep"].lower() == "kh")[:keep_n]

    natural = None
    critical = None
    if sides == 20 and len(kept) == 1:
        natural = kept[0]
        critical = "hit" if natural == 20 else "fail" if natural == 1 else None

    return RollResult(
        notation=notation.strip().lower(),
        rolls=rolls,
        kept=kept,
        modifier=modifier,
        total=sum(kept) + modifier,
        natural=natural,
        critical=critical,
    )


def roll_d20(
    modifier: int = 0,
    advantage: bool = False,
    disadvantage: bool = False,
    rng: random.Random | None = None,
) -> RollResult:
    """D&D 5e d20 roll. Advantage and disadvantage cancel each other out."""
    rng = rng or random
    if advantage and not disadvantage:
        mode, keep = "advantage", "kh"
    elif disadvantage and not advantage:
        mode, keep = "disadvantage", "kl"
    else:
        mode, keep = "normal", None

    sign = "+" if modifier >= 0 else "-"
    mod = f"{sign}{abs(modifier)}" if modifier else ""
    notation = f"2d20{keep}1{mod}" if keep else f"1d20{mod}"
    result = roll(notation, rng)
    result.detail["mode"] = mode
    return result
