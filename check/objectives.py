"""Compare pickup and supply routes on a simplified grid. Run: python check/objectives.py

Each trial starts with one known objective and no opponents. Movement uses the
kit's speed, acceleration, energy, jump, and gravity settings. Geometry uses
the bot's sampled grid. Only the official practice scorer measures placement.
"""
import argparse
import copy
import gzip
import json
import math
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot import Bot
from mechfight import draw
from motion import advance


def trial(hello, fixture, kind, rng, opponent=False):
    bot = Bot(hello)
    arena = bot.arena
    obs = copy.deepcopy(fixture)
    obs.update(mechs=[], cubes=[], pickups=[], crates=[], drops=[], events=[], sounds=[], projectiles=[], offer=None)
    me = obs["self"]
    for _ in range(1000):
        cell = rng.randrange(len(arena.height))
        x, y = arena.xy(cell)
        theta = rng.uniform(-math.pi, math.pi)
        distance = rng.uniform(20, 95)
        dest = arena.cell(x + distance * math.cos(theta), y + distance * math.sin(theta))
        tx, ty = arena.xy(dest)
        z, tz = arena.height[cell], arena.height[dest]
        valid_surface = kind != "drop" or abs(tz - arena.ground[dest]) < 1
        if valid_surface and math.dist((x, y), (tx, ty)) > 18 and abs(tz - z) < 36:
            break
    obj = {"id": 20001, "pos": [tx, ty, tz]}
    if opponent:
        a = rng.uniform(-math.pi, math.pi)
        ex, ey = arena.xy(arena.cell(tx + 50 * math.cos(a), ty + 50 * math.sin(a)))
        obs["mechs"] = [{"kind": "mech", "id": (me["id"] + 1) % 16, "hp": 1400,
                         "pos": [ex, ey, arena.height[arena.cell(ex, ey)]],
                         "vel": [0, 0, 0], "aim": [0, 0]}]
    if kind == "drop":
        obj.update(radius=8, holder=None, progress=0, capture_s=4, lands_in=0)
        obs["drops"] = [obj]
    elif kind == "weapon":
        obj.update(kind="laser")
        obs["pickups"] = [obj]
    else:
        obs["cubes"] = [obj]
    # The whole short trial is inside the current circle.
    obs["zone"].update(center=[tx, ty], radius=400, next_center=[tx, ty], next_radius=300,
                       shrink_start=60, shrink_end=120)
    me.update(pos=[x,y,z], vel=[0,0,0], grounded=True, energy=me["max_energy"])
    capture = 0.0
    last_spent = -100
    dt = 0.1
    for step in range(400):
        t = step * dt
        x, y, z = me["pos"]
        obs.update(t=t, tick=2*step)
        draw.clear()
        action = bot.act(obs)
        me["aim"] = action.get("aim", me["aim"])
        near = abs(tz-z) < 4 and math.hypot(tx-x, ty-y) < {"drop":8, "cube":3.5, "weapon":4}[kind]
        if kind == "drop":
            capture = capture + dt if near else 0
            obj.update(holder=me["id"] if near else None, progress=capture)
            if capture >= 4:
                return t
        elif near and (kind == "cube" or action.get("take") == obj["id"]):
            return t
        last_spent = advance(me, action, arena, t, dt, last_spent)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trials", type=int, default=24, help="Trials per objective")
    ap.add_argument("--seed", type=int, default=7081)
    ap.add_argument("--opponent", action="store_true", help="Show a stationary mech without applying damage")
    args = ap.parse_args()
    with gzip.open(ROOT / "check" / "stream.jsonl.gz", "rt") as stream:
        hello, fixture = json.loads(next(stream)), json.loads(next(stream))
    hello["map"]["dir"] = str(ROOT / "arena")
    for kind in ("cube", "weapon", "drop"):
        rng = random.Random(args.seed)
        times = [trial(hello, fixture, kind, rng, args.opponent) for _ in range(args.trials)]
        reached = [v for v in times if v is not None]
        median = f"{statistics.median(reached):.1f}s" if reached else "n/a"
        print(f"{kind}: {len(reached)}/{len(times)} reached in 40s, median {median}", flush=True)


if __name__ == "__main__":
    main()
