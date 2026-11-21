"""Paired closing-circle drills. Measure zone damage with distracting opponents.

Run with --bot-root pointing at an exported revision to compare controllers
on identical scenarios. Opponents move but deal no damage. This isolates the
cost of the zone and does not simulate or predict an official placement.
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


def run_trial(bot, obs, rng, center, radius, phase):
    me, zone = obs["self"], obs["zone"]
    angle = rng.uniform(-math.pi, math.pi)
    end_radius = phase["radius"]
    shift = rng.uniform(0.15, 0.90) * (radius - end_radius)
    end = [center[0] + shift * math.cos(angle), center[1] + shift * math.sin(angle)]
    angle = rng.uniform(-math.pi, math.pi)
    distance = radius * rng.uniform(0.35, 0.85)
    x, y = center[0] + distance * math.cos(angle), center[1] + distance * math.sin(angle)
    vx = vy = 0.0
    duration, dt = phase["shrink_s"], 0.1
    damage = 0.0
    energy = me["max_energy"]
    stats = me["stats"]
    level = bot.arena.height[bot.arena.cell(*center)]
    rivals = [rng.uniform(-math.pi, math.pi) for _ in range(2)]
    obs.update(crates=[], pickups=[], cubes=[], drops=[], sounds=[], events=[], beams=[], projectiles=[],
               alive=3, offer=None)
    start = 300.0
    for tick in range(round(duration/dt)):
        elapsed = tick * dt
        fraction = elapsed / duration
        cx = center[0] + fraction * (end[0] - center[0])
        cy = center[1] + fraction * (end[1] - center[1])
        r = radius + fraction * (end_radius - radius)
        inside = math.hypot(x-cx, y-cy) <= r
        if not inside:
            damage += phase["dps"]*dt
        me.update(pos=[x,y,level], vel=[vx,vy,0], in_zone=inside, grounded=True,
                  hp=max(1, me["max_hp"]-damage), energy=energy)
        zone.update(center=[cx,cy], next_center=end, radius=r, next_radius=end_radius,
                    shrink_start=start, shrink_end=start+duration, dps=phase["dps"])
        obs.update(t=start+elapsed, tick=round((start+elapsed)*20), mechs=[
            dict(id=(me["id"]+i+1)%16, kind="mech", hp=950, max_hp=1400, cubes=i,
                 pos=[cx+28*math.cos(a+elapsed*0.12), cy+28*math.sin(a+elapsed*0.12),level],
                 aim=[0,0], vel=[0,0,0], weapons=["gun"]) for i,a in enumerate(rivals)])
        action = bot.act(obs)
        me["aim"] = action["aim"]
        boost = action["boost"] and energy > 1
        energy = max(0, energy - stats["boost_drain"]*dt) if boost else min(me["max_energy"], energy+stats["energy_regen"]*dt)
        speed = stats["boost_speed"] if boost else stats["walk_speed"]
        ax, ay = speed*action["move"][0]-vx, speed*action["move"][1]-vy
        k = min(1, stats["ground_accel"]*dt/max(0.001, math.hypot(ax, ay)))
        vx, vy = vx+k*ax, vy+k*ay
        x, y = x+dt*vx, y+dt*vy
    return damage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--seed", type=int, default=7289)
    parser.add_argument("--trials", type=int, default=24)
    args = parser.parse_args()
    root = args.bot_root.resolve()
    sys.path.insert(0, str(root))
    from bot import Bot
    with gzip.open(root / "check" / "stream.jsonl.gz", "rt") as stream:
        hello, fixture = json.loads(next(stream)), json.loads(next(stream))
    hello["map"]["dir"] = str(root/"arena")
    rng = random.Random(args.seed)
    phases = hello["config"]["zone"]["phases"]
    for previous, phase in zip(phases[-3:-1], phases[-2:]):
        results = []
        for _ in range(args.trials):
            bot = Bot(hello)
            # Use an open patch so the drill measures ring decisions independently of wall physics.
            for attempt in range(500):
                center = bot.arena.xy(rng.randrange(len(bot.arena.height)))
                heights = [bot.arena.height[bot.arena.cell(center[0]+i,center[1]+j)]
                           for i in (-36,-18,0,18,36) for j in (-36,-18,0,18,36)]
                if max(heights)-min(heights) < 4 and abs(center[0]) < 380 and abs(center[1]) < 220:
                    break
            results.append(run_trial(bot, copy.deepcopy(fixture), rng, center, previous["radius"], phase))
        print(f'{previous["radius"]} to {phase["radius"]} m: mean zone damage {statistics.mean(results):.1f}, '
              f'max {max(results):.1f}, zero damage {results.count(0.0)}/{len(results)}', flush=True)


if __name__ == "__main__":
    main()
