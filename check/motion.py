"""Simplified movement on the bot's sampled terrain for the local drills."""
import math


def advance(me, action, arena, t, dt, last_spent):
    stats = me["stats"]
    x, y, z = me["pos"]
    vx, vy, vz = me["vel"]
    grounded, energy = me["grounded"], me["energy"]
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
    me.update(pos=[x, y, z], vel=[vx, vy, vz], grounded=grounded, energy=energy)
    return last_spent
