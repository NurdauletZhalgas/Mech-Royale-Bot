"""Choose a safe roof in the shrinking arena and collect the first available cube."""
import math

import mechfight as mf
from arena_map import Arena, Route
from example_bot import Bot as Starter


class Bot(Starter):
    name = "roof-runner"

    def __init__(self, hello: mf.Hello):
        super().__init__(hello)
        self.crate_height = hello["config"]["crates"]["height"]
        self.regen_delay = hello["config"]["mech"]["regen_delay"]
        self.first_shrink = hello["config"]["zone"]["phases"][0]["hold_s"]
        self.last_damage = -math.inf
        self.target_id = None
        self.target_since = 0.0
        self.abandoned = set()
        self.arena = Arena(hello["map"]["dir"])
        self.route = Route(self.arena)
        self.goal = None
        self.plan_at = 0
        self.phase = None
        self.last_pos = None
        self.check_motion_at = 0
        self.jet_until = -1
        self.orbit_phase = hello["slot"] * 0.39

    def opening(self, obs: mf.Observation) -> mf.Action:
        action = super().act(obs)
        me = obs["self"]
        now = obs["t"]
        if any(event["type"] == "damaged" for event in obs["events"]):
            self.last_damage = now
        if (me["cubes"] or now >= self.first_shrink or not me["in_zone"]
                or obs["mechs"] or now - self.last_damage < self.regen_delay):
            self.target_id = None
            return action

        # Bound the cost of following a pickup behind a wall or on a ledge.
        if self.target_id is not None and now - self.target_since > 6.0:
            self.abandoned.add(self.target_id)
            self.target_id = None

        x, y, z = me["pos"]
        zone = obs["zone"]
        for kind, items in (("cube", obs["cubes"]), ("crate", obs["crates"])):
            nearby = []
            for item in items:
                ix, iy, iz = item["pos"]
                distance = math.hypot(ix - x, iy - y)
                if item["id"] in self.abandoned or abs(iz - z) > 4 or distance > 40:
                    continue
                # Leave time to walk from the detour to the next circle.
                return_distance = max(0.0, math.dist((ix, iy), zone["next_center"]) - zone["next_radius"])
                travel_time = (distance + return_distance) / me["stats"]["walk_speed"]
                if now + travel_time + 6 < zone["shrink_end"]:
                    nearby.append((distance, item["id"], item))
            if not nearby:
                continue

            distance, item_id, item = min(nearby, key=lambda entry: entry[:2])
            if item_id != self.target_id:
                self.target_id, self.target_since = item_id, now
            ix, iy, iz = item["pos"]
            yaw = math.atan2(iy - y, ix - x)
            direction = 1
            pitch = 0.0
            fire = False
            if kind == "crate":
                # Give the starter gun a clear downward angle at close range.
                direction = -1 if distance < 12 else 0 if distance < 20 else 1
                pitch = math.atan2(iz + self.crate_height / 2 - z - me["stats"]["muzzle_height"], distance)
                yaw_error = math.remainder(yaw - me["aim"][0], math.tau)
                fire = abs(yaw_error) < 0.06 and abs(pitch - me["aim"][1]) < 0.06
            action.update(move=[direction * math.cos(yaw), direction * math.sin(yaw)],
                          aim=[yaw, pitch], fire=[fire, False], jump=False, boost=False)
            mf.draw.label(f"first {kind} {item_id}")
            return action

        self.target_id = None
        return action

    def act(self, obs: mf.Observation) -> mf.Action:
        action = self.opening(obs)
        if self.target_id is not None:
            return action
        me, zone, now = obs["self"], obs["zone"], obs["t"]
        x, y, z = me["pos"]
        if now >= self.plan_at or self.phase != zone["shrink_end"]:
            self.goal = self.arena.retreat(me["pos"], zone, self.goal)
            self.plan_at = now + 3
            self.phase = zone["shrink_end"]
        wx, wy, top = self.route.waypoint(me["pos"], self.goal, now)
        goal_dist = math.dist((x, y), self.goal)
        arrived = goal_dist < 7 and abs(z - self.arena.height[self.arena.cell(*self.goal)]) < 3
        if arrived:
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
        sprint = (not me["in_zone"] and me["grounded"] and ledge < 2 and me["energy"] > 30)
        scale = max(distance, 3)
        action.update(move=[dx / scale, dy / scale], jump=jet and me["grounded"],
                      boost=(jet and me["energy"] > 1) or sprint)
        if not any(m["kind"] == "mech" for m in obs["mechs"]):
            action["aim"] = [self.orbit_phase + now * 1.8 if arrived else math.atan2(dy, dx), 0]
        mf.draw.label("roof" if arrived else "climb" if jet else "route")
        return action


if __name__ == "__main__":
    mf.run(Bot)
