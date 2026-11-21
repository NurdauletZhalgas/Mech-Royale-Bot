"""Choose objectives from the game's visible pickups, upgrade offers, and drop timers."""
import math


UPGRADES = ("armor", "plating", "gun_damage", "gun_rate", "gun_mag", "nanites",
            "laser_damage", "lightning_range", "laser_charge", "servos",
            "gun_velocity", "reactor", "jets", "capacitor", "sensors", "gyros")
SECONDARY = {"laser": 3, "lightning": 2, "mortar": 1, "gun": 0}


class Economy:
    def __init__(self, config):
        self.pickup_radius = config["loot"]["pickup_radius"]
        self.crate_height = config["crates"]["height"]
        self.memory = {}
        self.ignored = {}
        self.chosen = None
        self.started = 0

    def select(self, obs, action):
        me, now, zone = obs["self"], obs["t"], obs["zone"]
        pos = me["pos"]
        if obs["offer"]:
            choices = obs["offer"]["choices"]
            action["pick"] = min(range(len(choices)), key=lambda i:
                                 UPGRADES.index(choices[i]["id"]) if choices[i]["id"] in UPGRADES else len(UPGRADES))
        secondary = me["weapons"][1]
        equipped = SECONDARY.get(secondary["kind"], 0) if secondary else 0
        for kind, objects in (("cube", obs["cubes"]), ("weapon", obs["pickups"]), ("crate", obs["crates"])):
            for item in objects:
                self.memory[item["id"]] = (kind, item, now)
                if (kind == "weapon" and SECONDARY.get(item["kind"], 0) > equipped
                        and abs(item["pos"][2] - pos[2]) < 4
                        and math.dist(pos[:2], item["pos"][:2]) < self.pickup_radius
                        and (not secondary or not secondary.get("charge", 0))):
                    action["take"] = item["id"]
                    if secondary:
                        action["drop"] = 1
        for event in obs["events"]:
            if event["type"] == "took" or (event["type"] == "take_failed" and event["reason"] == "gone"):
                self.memory.pop(event["id"], None)
        nearby_enemy = min((math.dist(pos, a["pos"]) for a in obs["mechs"] if a["kind"] == "mech"),
                           default=math.inf)
        candidates = []
        for item_id, (kind, item, seen) in list(self.memory.items()):
            d = math.dist(pos[:2], item["pos"][:2])
            if now - seen > 18 or (now > seen + 0.4 and d < 8 and abs(item["pos"][2] - pos[2]) < 4):
                del self.memory[item_id]
                continue
            if kind == "weapon":
                tier = SECONDARY.get(item["kind"], 0)
                if tier <= equipped:
                    continue
                value = (65 if equipped else 108) + tier * 14
            elif kind == "cube":
                value = 135 if me["cubes"] < 10 else 62
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
            value = 165 + 120 * (1 - me["hp"] / me["max_hp"]) + 20 * drop["progress"]
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
