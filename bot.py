"""Navigate the shrinking arena, earn upgrades, and contest supply drops."""
import math

import mechfight as mf
from arena_map import Arena, OpeningSearch, Route
from economy import Economy
from mobility import Movement


class Bot:
    name = "collector"

    def __init__(self, hello: mf.Hello):
        self.economy = Economy(hello["config"])
        self.mech_height = hello["config"]["mech"]["height"]
        self.cube_growth = hello["config"]["cubes"]["size_per_cube"]
        self.drone_height = hello["config"]["npc"]["height"]
        self.focus = None
        self.recovering = False
        self.arena = Arena(hello["map"]["dir"])
        self.search = OpeningSearch(self.arena, hello["slot"])
        self.opening_ends = hello["config"]["zone"]["phases"][0]["hold_s"]
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
        action = {"tick": obs["tick"]}
        me, zone, now = obs["self"], obs["zone"], obs["t"]
        x, y, z = me["pos"]
        if now >= self.plan_at or self.phase != zone["shrink_end"]:
            self.goal = self.arena.retreat(me["pos"], zone, self.goal)
            self.plan_at = now + 3
            self.phase = zone["shrink_end"]
        choice = self.economy.select(obs, action)
        purpose, item = choice if choice else ("roof", None)
        goal = tuple(item["pos"][:2]) if item else self.goal
        if (item is None and now < self.opening_ends and None in me["weapons"]
                and me["in_zone"] and me["hp"] >= 0.75 * me["max_hp"]
                and not any(actor["kind"] == "mech" for actor in obs["mechs"])):
            goal = self.search.destination(me["pos"], zone, now)
            purpose = "search"
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
        nearest_dist = min((math.dist(a["pos"], me["pos"]) for a in opponents), default=math.inf)
        hp_fraction = me["hp"] / max(me["max_hp"], 1)
        if hp_fraction < 0.47:
            self.recovering = True
        elif hp_fraction > 0.85:
            self.recovering = False
        action["aim"] = [self.orbit_phase + now * 1.8, 0]
        target_dist = math.inf
        if opponents:
            nearest = min(opponents, key=lambda a: math.dist(a["pos"], me["pos"]))
            enemy = self.choose_opponent(opponents, me)
            self.focus = enemy["id"]
            self.movement.duel(obs, nearest, goal, purpose, action, self.recovering, len(opponents))
            height = self.mech_height * (1 + self.cube_growth * enemy.get("cubes", 0))
            self.aim_at_prop(action, me, enemy["pos"], height * 0.5)
            target_dist = math.dist(enemy["pos"], me["pos"])
        else:
            self.focus = None
        visible_crate = purpose == "crate" and any(c["id"] == item["id"] for c in obs["crates"])
        if not opponents and visible_crate:
            self.aim_at_prop(action, me, item["pos"], self.economy.crate_height * 0.5)
            target_dist = math.dist(item["pos"], me["pos"])
            if goal_dist < 27 and abs(goal_z - z) < 4:
                factor = -1 if goal_dist < 12 else 0
                action.update(move=[factor * math.cos(action["aim"][0]), factor * math.sin(action["aim"][0])],
                              jump=False, boost=False)
        elif not opponents and obs["mechs"]:
            drone = min(obs["mechs"], key=lambda m: math.dist(m["pos"], me["pos"]))
            self.aim_at_prop(action, me, drone["pos"], self.drone_height * 0.5)
            target_dist = math.dist(drone["pos"], me["pos"])
        if self.recovering and me["in_zone"] and nearest_dist > 110:
            # Dealing any damage resets the game's HP regeneration timer.
            # Leave ambient drones and crates alone until recovery finishes.
            if not opponents or enemy.get("hp", me["max_hp"]) > me["max_hp"] * 0.30:
                target_dist = math.inf
            if purpose == "crate" and not opponents:
                action["move"] = [0.0, 0.0]
                action["jump"] = action["boost"] = False
        if not me["in_zone"] and not opponents:
            # Zone damage disables regeneration; spend the turn getting inside.
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
        mf.draw.label("recover" if self.recovering and target_dist == math.inf else purpose)
        return action

    def choose_opponent(self, opponents, me):
        def priority(actor):
            d = math.dist(me["pos"], actor["pos"])
            remaining = actor.get("hp", me["max_hp"])
            # In this game an elimination immediately improves placement, and
            # the defeated mech drops its accumulated cubes and two more.
            cost = 0.085 * remaining + 0.65 * d + max(0, d - 140)
            if actor["id"] == self.focus:
                cost -= 15
            return cost
        return min(opponents, key=priority)

    @staticmethod
    def aim_at_prop(action, me, pos, height):
        x, y, z = me["pos"]
        dx, dy = pos[0] - x, pos[1] - y
        action["aim"] = [math.atan2(dy, dx), math.atan2(pos[2] + height - z - me["stats"]["muzzle_height"],
                                                        math.hypot(dx, dy))]


if __name__ == "__main__":
    mf.run(Bot)
