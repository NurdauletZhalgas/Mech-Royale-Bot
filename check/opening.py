"""Measure time to fill the second slot in matched, opponent-free opening layouts.

The public rules set the loot count, types, roof fraction, view arc, proximity
and pickup range. Sight and movement use the sampled terrain. This drill ends
at the first floor pickup or 45 seconds. There are no crates, drones or rivals.
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

from motion import advance


ROOT = Path(__file__).resolve().parents[1]
LIMIT = 45.0


def trial(bot, config, fixture, rng):
    arena = bot.arena
    obs = copy.deepcopy(fixture)
    me, zone = obs["self"], obs["zone"]
    loot, vision = config["loot"], config["vision"]
    center, radius = zone["center"], zone["radius"]
    angle = rng.uniform(-math.pi, math.pi)
    offset = math.sqrt(rng.random()) * (radius-zone["next_radius"])
    zone["next_center"] = [center[0]+offset*math.cos(angle), center[1]+offset*math.sin(angle)]

    def position(roof, max_radius):
        while True:
            cell = rng.randrange(len(arena.height))
            x, y = arena.xy(cell)
            if ((arena.height[cell] > arena.ground[cell] + 3) == roof
                    and math.dist((x, y), center) <= max_radius):
                return [x, y, arena.height[cell]]

    me.update(pos=position(False, radius * config["match"]["spawn_zone_fraction"]),
              vel=[0, 0, 0], aim=[rng.uniform(-math.pi, math.pi), 0])
    kinds = list(loot["weights"])
    items = []
    for i in range(loot["floor_count"]):
        loc = position(rng.random() < loot["floor_roof_fraction"], radius)
        kind = rng.choices(kinds, weights=list(loot["weights"].values()))[0]
        items.append(dict(id=8000+i, kind=kind, pos=loc))
    obs.update(crates=[], mechs=[], events=[], drops=[], offer=None, cubes=[],
               projectiles=[], sounds=[], beams=[])
    clear = {}
    dt, last_spent = 0.1, -100.0
    for step in range(round(LIMIT / dt)):
        now = step * dt
        x, y, z = me["pos"]
        eye = z + me["stats"]["eye_height"]
        obs.update(t=now, tick=2*step, pickups=[])
        for item in items:
            px, py, pz = item["pos"]
            dx, dy = px-x, py-y
            distance = math.hypot(dx, dy)
            if distance > vision["range"]:
                continue
            if distance > vision["near_range"]:
                difference = math.remainder(math.atan2(dy, dx)-me["aim"][0], math.tau)
                if abs(difference) > math.radians(vision["fov_deg"]/2):
                    continue
            key = (arena.cell(x,y), round(eye/3), item["id"])
            if key not in clear:
                slices = max(1, math.ceil(distance/arena.step))
                clear[key] = all(
                    arena.height[arena.cell(x+dx*j/slices, y+dy*j/slices)] <
                    eye+(pz+1-eye)*j/slices for j in range(1, slices))
            if clear[key]:
                obs["pickups"].append(item)
        draw.clear()
        action = bot.act(obs)
        for item in obs["pickups"]:
            if (item["id"] == action.get("take") and abs(item["pos"][2]-z) <= 4
                    and math.dist((x,y), item["pos"][:2]) <= loot["pickup_radius"]):
                return now
        turn = math.remainder(action["aim"][0] - me["aim"][0], math.tau)
        cap = dt * me["stats"]["turn_rate"]
        me["aim"][0] += max(-cap, min(cap, turn))
        last_spent = advance(me, action, arena, now, dt, last_spent)
    return LIMIT


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot-root", type=Path, default=ROOT)
    parser.add_argument("--seed", type=int, default=20261121)
    parser.add_argument("--trials", type=int, default=64)
    args = parser.parse_args()
    sys.path.insert(0, str(args.bot_root.resolve()))
    from bot import Bot
    from mechfight import draw
    with gzip.open(ROOT / "check" / "stream.jsonl.gz", "rt") as f:
        hello, fixture = json.loads(next(f)), json.loads(next(f))
    hello["map"]["dir"] = str(ROOT/"arena")
    times = []
    for i in range(args.trials):
        rng = random.Random(args.seed+i)
        hello["slot"] = fixture["self"]["id"] = rng.randrange(16)
        times.append(trial(Bot(hello), hello["config"], fixture, rng))
    print(f"{sum(t<LIMIT for t in times)}/{len(times)} equipped in {LIMIT:g}s; "
          f"{sum(t<=15 for t in times)} by 15s; mean time with misses counted at "
          f"{LIMIT:g}s: {statistics.mean(times):.2f}s")
