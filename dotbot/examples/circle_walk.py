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
from dotbot.rest import RestClient, rest_client
from dotbot.websocket import DotBotWsClient

THRESHOLD = 20  # Acceptable distance error to consider a waypoint reached
DT = 0.5  # Control loop period (seconds)

# TODO: Measure these values for real dotbots
MAX_SPEED = 0.055  # Maximum allowed linear speed of a bot
async def walk_on_circle(
    client: RestClient,
    ws: DotBotWsClient,
    center: Vec2,
    radii: tuple[float, float],
) -> None:
    r_inner, r_outer = radii

    while True:
        dotbots = await client.fetch_active_dotbots()

        for bot in dotbots:
            px = bot.lh2_position.x
            py = bot.lh2_position.y

            # Vector from center
            dx = px - center.x
            dy = py - center.y

            dist = math.hypot(dx, dy)
            if dist == 0:
                continue

            # --- choose target radius ---
            target_radius = (
                r_inner
                if abs(dist - r_inner) < abs(dist - r_outer)
                else r_outer
            )

            # Unit radial vector
            ux = dx / dist
            uy = dy / dist

            # Clockwise tangent (−90° rotation)
            tx = -uy
            ty = ux

            # Tangential step
            step_x = tx * MAX_SPEED
            step_y = ty * MAX_SPEED

            # Candidate next position
            nx = px + step_x
            ny = py + step_y

            # --- HARD PROJECTION BACK TO CHOSEN CIRCLE ---
            ndx = nx - center.x
            ndy = ny - center.y
            ndist = math.hypot(ndx, ndy)

            if ndist > 0:
                nx = center.x + target_radius * (ndx / ndist)
                ny = center.y + target_radius * (ndy / ndist)
            # --------------------------------------------

            waypoints = DotBotWaypoints(
                threshold=THRESHOLD,
                waypoints=[DotBotLH2Position(x=nx, y=ny, z=0)],
            )

            # await client.send_waypoint_command(
            #     address=bot.address,
            #     application=ApplicationType.DotBot,
            #     command=waypoints,
            # )

            await ws.send(
                cmd="waypoints",
                address=bot.address,
                application="DotBot",
                data=waypoints.model_dump(),
            )


        await asyncio.sleep(DT)

async def main() -> None:
    url = os.getenv("DOTBOT_CONTROLLER_URL", "localhost")
    port = os.getenv("DOTBOT_CONTROLLER_PORT", "8000")
    use_https = os.getenv("DOTBOT_CONTROLLER_USE_HTTPS", False)
    client = RestClient(url, port, use_https)

    center = Vec2(x=0.5, y=0.5)
    radii = (0.3, 0.4)

    async with rest_client(url, port, use_https) as client:
        ws = DotBotWsClient(url, port)
        await ws.connect()
        try:
            await walk_on_circle(client, ws, center, radii)
        finally:
            await ws.close()



if __name__ == "__main__":
    asyncio.run(main())
