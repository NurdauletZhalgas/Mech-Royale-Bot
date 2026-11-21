"""Choose objectives from the game's visible pickups, upgrade offers, and drop timers."""
import math
from collections import Counter


UPGRADES = ("armor", "plating", "gun_damage", "gun_rate", "gun_mag", "nanites",
            "laser_damage", "lightning_range", "laser_charge", "servos",
            "gun_velocity", "reactor", "jets", "capacitor", "sensors", "gyros")
# Utility of each complete two-slot loadout. The two instant game abilities
# complement each other at different ranges and may occupy either slot.
LOADOUT = {frozenset(): 0,
           frozenset(["gun"]): 20, frozenset(["mortar"]): 12,
           frozenset(["laser"]): 40, frozenset(["lightning"]): 35,
           frozenset(["gun", "mortar"]): 34, frozenset(["mortar", "lightning"]): 49,
           frozenset(["laser", "mortar"]): 52, frozenset(["gun", "lightning"]): 62,
           frozenset(["gun", "laser"]): 68, frozenset(["laser", "lightning"]): 89}


def equipment_changes(slots):
    owned = {w["kind"] for w in slots if w}
    swaps = {}
    for kind in ("laser", "lightning", "mortar", "gun"):
        if kind in owned:
            continue
        best_gain = 0
        for i, old in enumerate(slots):
            if old and (None in slots or old.get("charge", 0)):
                continue
            other = slots[1 - i]
            pair = {kind, other["kind"]} if other else {kind}
            gain = LOADOUT[frozenset(pair)] - LOADOUT[frozenset(owned)]
            if gain > best_gain:
                best_gain = gain
                swaps[kind] = (gain, i)
    return swaps


class Economy:
    def __init__(self, config):
        self.pickup_radius = config["loot"]["pickup_radius"]
        self.crate_height = config["crates"]["height"]
        self.stat_cap = config["cubes"]["stat_cap"]
        self.thresholds = config["cubes"]["upgrade_thresholds"]
        self.memory = {}
        self.ignored = {}
        self.chosen = None
        self.started = 0

    def select(self, obs, action):
        me, now, zone = obs["self"], obs["t"], obs["zone"]
        pos = me["pos"]
        if obs["offer"]:
            choices = obs["offer"]["choices"]
            priority = list(UPGRADES)
            if "nanites" not in me["upgrades"] and me["hp"] < 0.7 * me["max_hp"] and zone["radius"] > 70:
                priority.insert(0, "nanites")
            if not me["upgrades"]:
                priority.insert(0, "plating")
            if "gun_mag" not in me["upgrades"]:
                priority.insert(priority.index("gun_damage"), "gun_mag")
            action["pick"] = min(range(len(choices)), key=lambda i:
                                 priority.index(choices[i]["id"]) if choices[i]["id"] in priority else len(priority))
        slots = me["weapons"]
        changes = equipment_changes(slots)
        best_take = 0
        for kind, objects in (("cube", obs["cubes"]), ("weapon", obs["pickups"]), ("crate", obs["crates"])):
            for item in objects:
                self.memory[item["id"]] = (kind, item, now)
                if (kind == "weapon" and item["kind"] in changes
                        and abs(item["pos"][2] - pos[2]) < 4
                        and math.dist(pos[:2], item["pos"][:2]) < self.pickup_radius):
                    gain, slot = changes[item["kind"]]
                    if gain > best_take:
                        action["take"], best_take = item["id"], gain
                        if slots[slot]:
                            action["drop"] = slot
        for event in obs["events"]:
            if event["type"] == "took" or (event["type"] == "take_failed" and event["reason"] == "gone"):
                self.memory.pop(event["id"], None)
        nearby_enemy = min((math.dist(pos, a["pos"]) for a in obs["mechs"] if a["kind"] == "mech"),
                           default=math.inf)
        # A defeated mech leaves several individually identified cubes. Estimate
        # the value of the whole nearby pile using two shifted spatial grids.
        def bins(point):
            x, y, z = point
            return ((0, math.floor(x/12), math.floor(y/12), math.floor(z/5)),
                    (1, math.floor((x+6)/12), math.floor((y+6)/12), math.floor((z+2.5)/5)))

        piles = Counter(key for cube in obs["cubes"] for key in bins(cube["pos"]))
        until_upgrade = next((threshold - me["cubes"] for threshold in self.thresholds
                              if threshold > me["cubes"]), math.inf)
        candidates = []
        for item_id, (kind, item, seen) in list(self.memory.items()):
            d = math.dist(pos[:2], item["pos"][:2])
            if now - seen > 18 or (now > seen + 0.4 and d < 8 and abs(item["pos"][2] - pos[2]) < 4):
                del self.memory[item_id]
                continue
            if kind == "weapon":
                if item["kind"] not in changes:
                    continue
                gain, _ = changes[item["kind"]]
                value = 62 + 1.9 * gain
            elif kind == "cube":
                count = max(1, *(piles[key] for key in bins(item["pos"])))
                useful = min(count, max(0, self.stat_cap - me["cubes"]))
                value = (135 + 23 * min(5, useful - 1)) if useful else 22
                if count >= until_upgrade:
                    value += 36
            else:
                if nearby_enemy < 90 or me["cubes"] >= 10 or d > 62:
                    continue
                value = 71
            candidates.append((value, kind, item, d, now - seen))
        for drop in obs.get("drops", []):
            d = math.dist(pos[:2], drop["pos"][:2])
            eta = d / me["stats"]["walk_speed"]
            if drop["lands_in"] > eta + 9:
                continue
            if drop["holder"] not in (None, me["id"]):
                time_to_ring = max(0, d - drop["radius"]) / me["stats"]["boost_speed"]
                if time_to_ring > drop["capture_s"] - drop["progress"] + 0.3:
                    continue
            progress = drop["progress"] if drop["holder"] == me["id"] else 0
            value = 188 + 150 * (1 - me["hp"] / me["max_hp"]) + 20 * progress
            candidates.append((value, "drop", drop, d, 0))
        best, choice = 0, None
        for value, kind, item, d, age in candidates:
            if now < self.ignored.get(item["id"], -1):
                continue
            target = item["pos"]
            outside = max(0, math.dist(target[:2], zone["next_center"]) - zone["next_radius"])
            if math.dist(target[:2], zone["center"]) > zone["radius"] or (
                    outside > 0 and now + (d + outside) / me["stats"]["walk_speed"] + 7 > zone["shrink_end"]):
                continue
            value -= d + outside * 0.55 + abs(pos[2] - target[2]) * 1.25 + age * 1.5
            if self.chosen == item["id"]:
                value += 14
            if nearby_enemy < 80 and kind != "drop" and d > 24:
                value -= 65
            if value > best:
                best, choice = value, (kind, item)
        chosen = choice[1]["id"] if choice else None
        if chosen != self.chosen:
            self.chosen, self.started = chosen, now
        elif chosen is not None and now - self.started > 19 and choice[0] != "drop":
            self.ignored[chosen] = now + 30
            self.chosen = None
            return None
        return choice
