"""Check whether the full bot takes or declines a recovery window in controlled observations."""
import copy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot import Bot
from mechfight import draw


def probe(hello, fixture, *, initial=9, alive=8, health=0.64, rival_hp=1400,
          distance=120, events=(), in_zone=True, elapsed=1.0):
    obs = copy.deepcopy(fixture)
    obs.update(mechs=[], crates=[], cubes=[], pickups=[], drops=[], projectiles=[],
               events=[], offer=None, alive=initial, t=110, tick=2200)
    me = obs["self"]
    me.update(hp=me["max_hp"] * health, in_zone=in_zone)
    x, y, z = me["pos"]
    obs["zone"].update(center=[x,y], next_center=[x,y], radius=300, next_radius=180,
                       shrink_start=140, shrink_end=180)
    obs["mechs"] = [dict(kind="mech", id=(me["id"]+1) % 16, pos=[x-distance,y,z],
                         hp=rival_hp, max_hp=1400, cubes=0, vel=[0,0,0])]
    bot = Bot(hello)
    draw.clear()
    bot.act(obs)
    obs.update(t=111, tick=2220, alive=alive, events=list(events))
    draw.clear()
    action = bot.act(obs)
    if elapsed > 1:
        obs.update(t=110+elapsed, tick=round((110+elapsed)*20), events=[])
        draw.clear()
        action = bot.act(obs)
    return not any(action["fire"])


if __name__ == "__main__":
    with gzip.open(ROOT/"check"/"stream.jsonl.gz", "rt") as f:
        hello, fixture = json.loads(next(f)), json.loads(next(f))
    hello["map"]["dir"] = str(ROOT/"arena")
    cases = [
        ("other player eliminated", True, {}),
        ("field stable", False, {"alive":9}),
        ("own elimination", False, {"events":[{"type":"kill","target":7}]}),
        ("one own and one independent elimination", True,
         {"initial":10,"events":[{"type":"kill","target":7}]}),
        ("incoming damage", False, {"events":[{"type":"damaged","amount":60,"by":1}]}),
        ("weak nearby rival", False, {"rival_hp":150}),
        ("rival inside proximity radius", False, {"distance":30}),
        ("outside zone", False, {"in_zone":False}),
        ("near full health", False, {"health":0.92}),
        ("heads up", False, {"initial":3,"alive":2}),
        ("quiet window expired", False, {"elapsed":22}),
    ]
    for label, expected, inputs in cases:
        actual = probe(hello, fixture, **inputs)
        if actual != expected:
            raise AssertionError(f"{label}: expected hold={expected}, got {actual}")
    print(f"{len(cases)} placement decisions passed")
