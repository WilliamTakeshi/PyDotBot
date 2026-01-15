import asyncio
import random
import os
import colorsys

from dotbot.models import (
    DotBotLH2Position,
    DotBotRgbLedCommandModel,
    DotBotWaypoints,
)
from dotbot.protocol import ApplicationType
from dotbot.rest import RestClient, rest_client_ctx

THRESHOLD = 20  # Acceptable distance error to consider a waypoint reached

async def blinky(
    client: RestClient,
) -> None:
    dotbots = await client.fetch_active_dotbots()

    while True:
        tasks = []
        for dotbot in dotbots:
            # Hue in [0, 1)
            hue = random.random()

            # Full saturation, full value → vivid colors
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)

            tasks.append(
                client.send_rgb_led_command(
                    address=dotbot.address,
                    command=DotBotRgbLedCommandModel(
                        red=int(r * 255),
                        green=int(g * 255),
                        blue=int(b * 255),
                    )
                )
            )
        await asyncio.gather(*tasks)

        waypoints = DotBotWaypoints(
            threshold=THRESHOLD,
            waypoints=[
                DotBotLH2Position(
                    x=dotbots[0].lh2_position.x, y=dotbots[0].lh2_position.y, z=0
                )
            ],
        )
        await client.send_waypoint_command(
            address=dotbots[0].address,
            application=ApplicationType.DotBot,
            command=waypoints,
        )

        print("AAAAA")

        # await asyncio.sleep(0.1)


async def main() -> None:
    url = os.getenv("DOTBOT_CONTROLLER_URL", "localhost")
    port = os.getenv("DOTBOT_CONTROLLER_PORT", "8000")
    use_https = os.getenv("DOTBOT_CONTROLLER_USE_HTTPS", False)
    async with rest_client_ctx(url, port, use_https) as client:
        await blinky(client)
    

if __name__ == "__main__":
    asyncio.run(main())
