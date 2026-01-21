import asyncio
import random
import os
import colorsys

from dotbot.models import (
    DotBotLH2Position,
    DotBotWaypoints,
)
from dotbot.rest import RestClient, rest_client
from dotbot.websocket import DotBotWsClient

THRESHOLD = 20  # Acceptable distance error to consider a waypoint reached

async def blinky(
    client: RestClient,
    ws: DotBotWsClient,
) -> None:
    dotbots = await client.fetch_active_dotbots()

    while True:
    # for _ in range(10):
        for dotbot in dotbots:
            # Hue in [0, 1)
            hue = random.random()

            # Full saturation, full value → vivid colors
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)

            await ws.send(
                cmd="rgb_led",
                address=dotbot.address,
                application="DotBot",
                data={
                    "red": int(r * 255),
                    "green": int(g * 255),
                    "blue": int(b * 255),
                },
            )

        waypoints = DotBotWaypoints(
            threshold=THRESHOLD,
            waypoints=[
                DotBotLH2Position(
                    x=dotbots[0].lh2_position.x, y=dotbots[0].lh2_position.y, z=0
                )
            ],
        )

        await ws.send(
            cmd="waypoints",
            address=dotbots[0].address,
            application="DotBot",
            data=waypoints.model_dump(),
        )

        print("AAAAA")

        await asyncio.sleep(0.25)

async def main() -> None:
    url = os.getenv("DOTBOT_CONTROLLER_URL", "localhost")
    port = os.getenv("DOTBOT_CONTROLLER_PORT", "8000")
    use_https = os.getenv("DOTBOT_CONTROLLER_USE_HTTPS", False)

    async with rest_client(url, port, use_https) as client:
        ws = DotBotWsClient(url, port)
        await ws.connect()
        try:
            await blinky(client, ws)
        finally:
            await ws.close()


if __name__ == "__main__":
    asyncio.run(main())
