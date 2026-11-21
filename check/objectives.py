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


def trial(hello, fixture, kind, rng, opponent=False, announced=False):
    from bot import Bot
    from mechfight import draw
    bot = Bot(hello)
    arena = bot.arena
    obs = copy.deepcopy(fixture)
    obs.update(mechs=[], cubes=[], pickups=[], crates=[], drops=[], events=[], sounds=[], projectiles=[], offer=None)
    me = obs["self"]
    stats = me["stats"]
    for _ in range(1000):
        cell = rng.randrange(len(arena.height))
        x, y = arena.xy(cell)
        theta = rng.uniform(-math.pi, math.pi)
        distance = rng.uniform(80, 320) if announced else rng.uniform(20, 95)
        dest = arena.cell(x + distance * math.cos(theta), y + distance * math.sin(theta))
        tx, ty = arena.xy(dest)
        z, tz = arena.height[cell], arena.height[dest]
        valid_surface = kind != "drop" or abs(tz - arena.ground[dest]) < 1
        if valid_surface and math.dist((x, y), (tx, ty)) > (70 if announced else 18) and abs(tz - z) < 36:
            break
    obj = {"id": 20001, "pos": [tx, ty, tz]}
    drops = hello["config"]["drops"]
    start = drops["times"][0] if announced else 0
    flight = drops["fall_s"] if announced else 0
    if opponent:
        a = rng.uniform(-math.pi, math.pi)
        ex, ey = arena.xy(arena.cell(tx + 50 * math.cos(a), ty + 50 * math.sin(a)))
        obs["mechs"] = [{"kind": "mech", "id": (me["id"] + 1) % 16, "hp": 1400,
                         "pos": [ex, ey, arena.height[arena.cell(ex, ey)]],
                         "vel": [0, 0, 0], "aim": [0, 0]}]
    if kind == "drop":
        obj.update(radius=drops["radius"], holder=None, progress=0, capture_s=drops["capture_s"], lands_in=flight)
        obs["drops"] = [obj]
    elif kind == "weapon":
        obj.update(kind="laser")
        obs["pickups"] = [obj]
    else:
        obs["cubes"] = [obj]
    # The whole short trial is inside the current circle.
    obs["zone"].update(center=[tx, ty], radius=400, next_center=[tx, ty], next_radius=300,
                       shrink_start=start+60, shrink_end=start+120)
    vx = vy = vz = 0.0
    capture = 0.0
    last_spent = -100
    energy = me["max_energy"]
    grounded = True
    dt = 0.1
    for step in range(400):
        t = step * dt
        me.update(pos=[x,y,z], vel=[vx,vy,vz], grounded=grounded, energy=energy)
        obs.update(t=start+t, tick=round(20*(start+t)))
        if kind == "drop":
            obj["lands_in"] = max(0, flight-t)
        draw.clear()
        action = bot.act(obs)
        me["aim"] = action.get("aim", me["aim"])
        near = abs(tz-z) < 4 and math.hypot(tx-x, ty-y) < {"drop":drops["radius"], "cube":3.5, "weapon":4}[kind]
        if kind == "drop":
            capture = capture + dt if near and t >= flight else 0
            obj.update(holder=me["id"] if capture else None, progress=capture)
            if capture >= obj["capture_s"]:
                return t
        elif near and (kind == "cube" or action.get("take") == obj["id"]):
            return t
        boost = action.get("boost", False) and energy > 0
        speed = stats["boost_speed"] if grounded and boost else stats["walk_speed"]
        mx, my = action.get("move", [0,0])
        dvx, dvy = speed*mx-vx, speed*my-vy
        accel = stats["ground_accel" if grounded else "air_accel"] * dt
        scale = min(1, accel / max(0.001, math.hypot(dvx, dvy)))
        vx, vy = vx + dvx*scale, vy + dvy*scale
        if grounded and action.get("jump"):
            grounded, vz = False, stats["jump_speed"]
        if boost and (not grounded or abs(mx)+abs(my)>0.1):
            energy = max(0, energy - dt*stats["boost_drain" if grounded else "jet_drain"])
            last_spent = t
        elif t-last_spent >= stats["energy_regen_delay"]:
            energy = min(me["max_energy"], energy+dt*stats["energy_regen"])
        if not grounded:
            vz += dt*((stats["jet_accel"] if boost else 0) - stats["gravity"])
            vz = min(vz, stats["max_rise_speed"])
        z += vz*dt
        nx, ny = x+vx*dt, y+vy*dt
        if arena.height[arena.cell(nx, y)] <= z + stats["step_up"]:
            x = nx
        else:
            vx = 0
        if arena.height[arena.cell(x, ny)] <= z + stats["step_up"]:
            y = ny
        else:
            vy = 0
        floor = arena.height[arena.cell(x, y)]
        grounded = z <= floor+0.05 and vz <= 0
        if grounded:
            z, vz = floor, 0
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trials", type=int, default=24, help="Trials per objective")
    ap.add_argument("--seed", type=int, default=7081)
    ap.add_argument("--opponent", action="store_true", help="Show a stationary mech without applying damage")
    ap.add_argument("--announced", action="store_true", help="Start far from a drop at the instant it is called")
    ap.add_argument("--bot-root", type=Path, default=ROOT, help="Bot checkout to run on the same layouts")
    args = ap.parse_args()
    sys.path.insert(0, str(args.bot_root.resolve()))
    with gzip.open(ROOT / "check" / "stream.jsonl.gz", "rt") as stream:
        hello, fixture = json.loads(next(stream)), json.loads(next(stream))
    hello["map"]["dir"] = str(ROOT / "arena")
    for kind in (("drop",) if args.announced else ("cube", "weapon", "drop")):
        rng = random.Random(args.seed)
        times = [trial(hello, fixture, kind, rng, args.opponent, args.announced) for _ in range(args.trials)]
        reached = [v for v in times if v is not None]
        median = f"{statistics.median(reached):.1f}s" if reached else "n/a"
        print(f"{kind}: {len(reached)}/{len(times)} reached in 40s, median {median}", flush=True)
        if args.announced:
            deadline = hello["config"]["drops"]["fall_s"] + 7
            print(f"captured by {deadline:g}s: {sum(t <= deadline for t in reached)}/{len(times)}")


if __name__ == "__main__":
    main()
