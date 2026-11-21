"""Navigate the shrinking arena, earn upgrades, and contest supply drops."""
import math

import mechfight as mf
from arena_map import Arena, Route
from economy import Economy
from mobility import Movement
from example_bot import Bot as Starter


class Bot(Starter):
    name = "twin-core"

    def __init__(self, hello: mf.Hello):
        super().__init__(hello)
        self.economy = Economy(hello["config"])
        self.arena = Arena(hello["map"]["dir"])
        self.movement = Movement(self.arena, hello["slot"])
        self.route = Route(self.arena)
        self.goal = None
        self.plan_at = 0
        self.phase = None
        self.last_pos = None
        self.check_motion_at = 0
        self.jet_until = -1
        self.travel_sprint = False
        self.orbit_phase = hello["slot"] * 0.39

    def act(self, obs: mf.Observation) -> mf.Action:
        action = super().act(obs)
        action.pop("take", None)
        me, zone, now = obs["self"], obs["zone"], obs["t"]
        x, y, z = me["pos"]
        if now >= self.plan_at or self.phase != zone["shrink_end"]:
            self.goal = self.arena.retreat(me["pos"], zone, self.goal)
            self.plan_at = now + 3
            self.phase = zone["shrink_end"]
        choice = self.economy.select(obs, action)
        purpose, item = choice if choice else ("roof", None)
        goal = tuple(item["pos"][:2]) if item else self.goal
        wx, wy, top = self.route.waypoint(me["pos"], goal, now)
        goal_dist = math.dist((x, y), goal)
        goal_z = item["pos"][2] if item else self.arena.height[self.arena.cell(*goal)]
        arrived = goal_dist < 7 and abs(z - goal_z) < 3
        if arrived and purpose == "roof":
            # Keep moving on broad rooftops, within the next circle and away from ledges.
            phase = self.orbit_phase + now * 0.52
            reach = min(7.5, max(0, zone["next_radius"] - 3))
            ox = self.goal[0] + reach * math.cos(phase)
            oy = self.goal[1] + reach * math.sin(phase)
            if (abs(self.arena.height[self.arena.cell(ox, oy)] - z) < 2
                    and math.dist((ox, oy), zone["next_center"]) <= zone["next_radius"]):
                wx, wy = ox, oy
            else:
                wx, wy = self.goal
        elif goal_dist < 10 and item:
            wx, wy, top = *goal, goal_z
        if (purpose == "drop" and me["grounded"] and goal_dist < item["radius"] * 0.65
                and abs(z - goal_z) < 2):
            wx, wy = x, y
        dx, dy = wx - x, wy - y
        distance = math.hypot(dx, dy)
        if now >= self.check_motion_at:
            if (not arrived and self.last_pos is not None
                    and math.dist((x, y), self.last_pos) < 2 and me["energy"] > 22):
                self.jet_until = now + 1.25
            self.last_pos, self.check_motion_at = (x, y), now + 0.8
        ledge = top - z
        jump_clearance = me["stats"]["jump_speed"] ** 2 / (2 * me["stats"]["gravity"])
        energy_for_climb = max(0, ledge - jump_clearance) * (
            me["stats"]["jet_drain"] / me["stats"]["max_rise_speed"])
        climb = (not arrived and distance < 14 and ledge > me["stats"]["step_up"]
                 and (not me["grounded"] or me["energy"] >= min(me["max_energy"] - 1, energy_for_climb + 6)))
        jet = climb or (not arrived and now < self.jet_until)
        energy_ratio = me["energy"] / max(1, me["max_energy"])
        if energy_ratio < 0.62:
            self.travel_sprint = False
        elif energy_ratio > 0.92:
            self.travel_sprint = True
        sprint = (me["grounded"] and ledge < 2 and goal_dist > 13
                  and ((not me["in_zone"] and me["energy"] > 30) or self.travel_sprint))
        scale = max(distance, 3)
        action.update(move=[dx / scale, dy / scale], jump=jet and me["grounded"],
                      boost=(jet and me["energy"] > 1) or sprint)
        opponents = [m for m in obs["mechs"] if m["kind"] == "mech"]
        if opponents:
            closest = min(opponents, key=lambda m: math.dist(m["pos"], me["pos"]))
            self.movement.duel(obs, closest, goal, purpose, action)
        if not opponents:
            action["aim"] = [self.orbit_phase + now * 1.8, 0]
        visible_crate = purpose == "crate" and any(c["id"] == item["id"] for c in obs["crates"])
        if not opponents and visible_crate:
            self.aim_at_prop(action, me, item["pos"], self.economy.crate_height * 0.5)
            if goal_dist < 27 and abs(goal_z - z) < 4:
                factor = -1 if goal_dist < 12 else 0
                action.update(move=[factor * math.cos(action["aim"][0]), factor * math.sin(action["aim"][0])],
                              jump=False, boost=False)
        elif not opponents and obs["mechs"]:
            drone = min(obs["mechs"], key=lambda m: math.dist(m["pos"], me["pos"]))
            self.aim_at_prop(action, me, drone["pos"], 1.75)
        if opponents:
            target_dist = math.dist(closest["pos"], me["pos"])
        elif visible_crate:
            target_dist = math.dist(item["pos"], me["pos"])
        elif obs["mechs"]:
            target_dist = math.dist(drone["pos"], me["pos"])
        else:
            target_dist = math.inf
        fire = [False, False]
        for i, weapon in enumerate(me["weapons"]):
            if not weapon:
                continue
            kind, stats = weapon["kind"], weapon["stats"]
            if kind == "gun":
                fire[i] = target_dist <= stats["range"]
                if target_dist > stats["range"] and weapon.get("ammo", 99) < stats["mag"] * 0.7:
                    action["reload"] = True
            elif kind == "laser":
                fire[i] = target_dist < stats["range"] and weapon.get("charge", 0) < stats["charge"] * 0.92
            elif kind == "lightning":
                fire[i] = target_dist < stats["range"] and me["energy"] >= stats["energy"]
            elif kind == "mortar":
                fire[i] = 25 < target_dist < 105
        action["fire"] = fire
        mf.draw.label(purpose)
        return action

    @staticmethod
    def aim_at_prop(action, me, pos, height):
        x, y, z = me["pos"]
        dx, dy = pos[0] - x, pos[1] - y
        action["aim"] = [math.atan2(dy, dx), math.atan2(pos[2] + height - z - me["stats"]["muzzle_height"],
                                                        math.hypot(dx, dy))]
        action["fire"] = [True, False]


if __name__ == "__main__":
    mf.run(Bot)
