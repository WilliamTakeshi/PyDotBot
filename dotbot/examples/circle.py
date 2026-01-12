import asyncio
import math
import os
from typing import Dict, List
import colorsys

from dotbot.examples.orca import (
    Agent,
    OrcaParams,
    compute_orca_velocity_for_agent,
)
from dotbot.examples.vec2 import Vec2
from dotbot.models import (
    DotBotLH2Position,
    DotBotModel,
    DotBotRgbLedCommandModel,
    DotBotWaypoints,
)
from dotbot.protocol import ApplicationType
from dotbot.rest import RestClient

THRESHOLD = 30  # Acceptable distance error to consider a waypoint reached
DT = 0.1  # Control loop period (seconds)

# TODO: Measure these values for real dotbots
BOT_RADIUS = 0.04  # Physical radius of a DotBot (unit), used for collision avoidance
MAX_SPEED = 0.04  # Maximum allowed linear speed of a bot

async def run_convergence(
    params: OrcaParams,
    client: RestClient,
) -> None:
    dotbots = await client.fetch_active_dotbots()
    dotbot_len = len(dotbots)


    for i, dotbot in enumerate(dotbots):
        # Hue in [0, 1)
        hue = i / dotbot_len

        # Full saturation, full value → vivid colors
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)

        await client.send_rgb_led_command(
            address=dotbot.address,
            command=DotBotRgbLedCommandModel(
                red=int(r * 255),
                green=int(g * 255),
                blue=int(b * 255),
        ),
    )

    # Send everyone to the same point
    await swap_positions(client, dotbots, params)

    return None


async def swap_positions(
    client: RestClient,
    dotbots: List[DotBotModel],
    params: OrcaParams,
) -> None:
    dotbot_len = len(dotbots)
    assert (dotbot_len % 2 == 0)
    goals = {}
    for index, bot in enumerate(dotbots):
        opposite_index = (index + dotbot_len//2) % dotbot_len

        goals[bot.address] = dotbots[opposite_index].lh2_position
    await send_to_goal(client, goals, params)


async def send_to_goal(
    client: RestClient,
    goals: Dict[str, Vec2],
    params: OrcaParams,
) -> None:
    while True:
        dotbots = await client.fetch_active_dotbots()
        agents: List[Agent] = []

        for bot in dotbots:
            bot_pref_vel = preferred_vel(
                dotbot=bot, goal=goals.get(bot.address)
            )
            estimated_vel = estimate_velocity_from_history(
                bot.position_history,
                dt=DT
            )
            # print(f"bot.address: {bot.address} bot.lh2_position.x: {bot.lh2_position.x}, bot.lh2_position.y: {bot.lh2_position.y}")
            agents.append(
                Agent(
                    id=bot.address,
                    position=Vec2(x=bot.lh2_position.x, y=bot.lh2_position.y),
                    velocity=estimated_vel,
                    radius=BOT_RADIUS,
                    max_speed=MAX_SPEED,
                    preferred_velocity=bot_pref_vel,
                )
            )

        queue_ready = all(
            a.preferred_velocity.x == 0 and a.preferred_velocity.y == 0 for a in agents
        )
        if queue_ready:
            break
        for agent in agents:
            neighbors = [neighbor for neighbor in agents if neighbor.id != agent.id]

            orca_vel = compute_orca_velocity_for_agent(agent, neighbors=neighbors, params=params)
            step = Vec2(x=orca_vel.x, y=orca_vel.y)

            # ---- CLAMP STEP TO GOAL DISTANCE ----
            goal = goals.get(agent.id)
            if goal is not None:
                dx = goal.x - agent.position.x
                dy = goal.y - agent.position.y
                dist_to_goal = math.hypot(dx, dy)

                step_len = math.hypot(step.x, step.y)
                if step_len > dist_to_goal and step_len > 0:
                    scale = dist_to_goal / step_len
                    step = Vec2(x=step.x * scale, y=step.y * scale)
            # ------------------------------------

            waypoints = DotBotWaypoints(
                threshold=THRESHOLD,
                waypoints=[
                    DotBotLH2Position(
                        x=agent.position.x + step.x, y=agent.position.y + step.y, z=0
                    )
                ],
            )
            await client.send_waypoint_command(
                address=agent.id,
                application=ApplicationType.DotBot,
                command=waypoints,
            )
        await asyncio.sleep(DT)
    return None


def preferred_vel(dotbot: DotBotModel, goal: Vec2 | None) -> Vec2:
    if goal is None:
        return Vec2(x=0, y=0)

    dx = goal.x - dotbot.lh2_position.x
    dy = goal.y - dotbot.lh2_position.y
    dist = math.sqrt(dx * dx + dy * dy)

    dist1000 = dist * 1000
    # If close to goal, stop
    if dist1000 < THRESHOLD:
        return Vec2(x=0, y=0)

    # Right-hand rule bias
    bias_angle = 0.0
    # Bot can only walk on a cone [-30, 30] in front of himself
    max_deviation = math.radians(30)

    # Convert bot direction into radians
    direction = direction_to_rad(dotbot.direction)

    # Angle to goal
    angle_to_goal = math.atan2(dy, dx) + bias_angle

    delta = angle_to_goal - direction
    # Wrap to [-π, +π]
    delta = math.atan2(math.sin(delta), math.cos(delta))

    # Clamp delta to [-MAX, +MAX]
    if delta > max_deviation:
        delta = max_deviation
    if delta < -max_deviation:
        delta = -max_deviation

    # Final allowed direction
    final_angle = direction + delta
    result = Vec2(
        x=math.cos(final_angle) * MAX_SPEED, y=math.sin(final_angle) * MAX_SPEED
    )
    return result


def direction_to_rad(direction: float) -> float:
    rad = (direction + 90) * math.pi / 180.0
    return math.atan2(math.sin(rad), math.cos(rad))  # normalize to [-π, π]

def estimate_velocity_from_history(
    history: list[DotBotLH2Position],
    dt: float,
) -> Vec2:
    """
    Estimate velocity using the last two positions.
    """
    if len(history) < 2:
        return Vec2(0.0, 0.0)

    p_prev = history[-2]
    p_curr = history[-1]

    return Vec2(
        x=(p_curr.x - p_prev.x) / dt,
        y=(p_curr.y - p_prev.y) / dt,
    )


async def main() -> None:
    params = OrcaParams(time_horizon=DT)
    url = os.getenv("DOTBOT_CONTROLLER_URL", "localhost")
    port = os.getenv("DOTBOT_CONTROLLER_PORT", "8000")
    use_https = os.getenv("DOTBOT_CONTROLLER_USE_HTTPS", False)
    client = RestClient(url, port, use_https)

    await run_convergence(params, client)


if __name__ == "__main__":
    asyncio.run(main())
