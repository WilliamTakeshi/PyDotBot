# SPDX-FileCopyrightText: 2022-present Inria
# SPDX-FileCopyrightText: 2022-present Alexandre Abadie <alexandre.abadie@inria.fr>
#
# SPDX-License-Identifier: BSD-3-Clause

"""Module for the web server application."""

import asyncio
import os
import traceback
from typing import Dict, List

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import math

from dotbot import pydotbot_version
from dotbot.logger import LOGGER
from dotbot.models import (
    DotBotLH2Position,
    DotBotModel,
    DotBotMoveRawCommandModel,
    DotBotNotificationCommand,
    DotBotNotificationModel,
    DotBotQueryModel,
    DotBotRgbLedCommandModel,
    DotBotStatus,
    DotBotWaypoints,
)
from dotbot.orca import Agent, OrcaParams, compute_orca_velocity_for_agent
from dotbot.protocol import (
    ApplicationType,
    PayloadCommandMoveRaw,
    PayloadCommandRgbLed,
    PayloadGPSPosition,
    PayloadGPSWaypoints,
    PayloadLH2Location,
    PayloadLH2Waypoints,
)
from dotbot.vec2 import Vec2

PYDOTBOT_FRONTEND_BASE_URL = os.getenv(
    "PYDOTBOT_FRONTEND_BASE_URL", "https://dotbots.github.io/PyDotBot"
)

class ReverseProxyMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/pin"):
            headers = {k: v for k, v in request.headers.items()}
            url = f"http://localhost:8080{request.url.path}"

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        url,
                        headers=headers,
                    )
                except httpx.ConnectError as exc:
                    LOGGER.warning(exc)
                    return Response(status_code=502, content=b"Proxy connection failed")

                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=response.headers,
                )

        response = await call_next(request)
        return response


api = FastAPI(
    debug=1,
    title="DotBot controller API",
    description="This is the DotBot controller API",
    version=pydotbot_version(),
    docs_url="/api",
    redoc_url=None,
)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api.add_middleware(ReverseProxyMiddleware)

@api.exception_handler(Exception)
async def print_exceptions(request: Request, exc: Exception):
    print("\n=== EXCEPTION CAUGHT ===")
    traceback.print_exc()  # <-- full traceback printed to terminal
    print("========================\n")

    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )



@api.put(
    path="/controller/dotbots/{address}/{application}/move_raw",
    summary="Move the dotbot",
    tags=["dotbots"],
)
async def dotbots_move_raw(
    address: str, application: int, command: DotBotMoveRawCommandModel
):
    """Set the current active DotBot."""
    if address not in api.controller.dotbots:
        raise HTTPException(status_code=404, detail="No matching dotbot found")

    payload = PayloadCommandMoveRaw(
        left_x=command.left_x,
        left_y=command.left_y,
        right_x=command.right_x,
        right_y=command.right_y,
    )
    api.controller.send_payload(int(address, 16), payload)
    api.controller.dotbots[address].move_raw = command


@api.put(
    path="/controller/dotbots/{address}/{application}/rgb_led",
    summary="Set the dotbot RGB LED color",
    tags=["dotbots"],
)
async def dotbots_rgb_led(
    address: str, application: int, command: DotBotRgbLedCommandModel
):
    """Set the current active DotBot."""
    if address not in api.controller.dotbots:
        raise HTTPException(status_code=404, detail="No matching dotbot found")

    payload = PayloadCommandRgbLed(
        red=command.red, green=command.green, blue=command.blue
    )
    api.controller.send_payload(int(address, 16), payload)
    api.controller.dotbots[address].rgb_led = command


@api.put(
    path="/controller/dotbots/{address}/{application}/waypoints",
    summary="Set the dotbot control mode",
    tags=["dotbots"],
)
async def dotbots_waypoints(
    address: str,
    application: int,
    waypoints: DotBotWaypoints,
):
    """Set the waypoints of a DotBot."""
    if address not in api.controller.dotbots:
        raise HTTPException(status_code=404, detail="No matching dotbot found")

    waypoints_list = waypoints.waypoints
    if application == ApplicationType.SailBot.value:
        if api.controller.dotbots[address].gps_position is not None:
            waypoints_list = [
                api.controller.dotbots[address].gps_position
            ] + waypoints.waypoints
        payload = PayloadGPSWaypoints(
            threshold=waypoints.threshold,
            count=len(waypoints.waypoints),
            waypoints=[
                PayloadGPSPosition(
                    latitude=int(waypoint.latitude * 1e6),
                    longitude=int(waypoint.longitude * 1e6),
                )
                for waypoint in waypoints.waypoints
            ],
        )
    else:  # DotBot application
        if api.controller.dotbots[address].lh2_position is not None:
            waypoints_list = [
                api.controller.dotbots[address].lh2_position
            ] + waypoints.waypoints
        payload = PayloadLH2Waypoints(
            threshold=waypoints.threshold,
            count=len(waypoints.waypoints),
            waypoints=[
                PayloadLH2Location(
                    pos_x=int(waypoint.x * 1e6),
                    pos_y=int(waypoint.y * 1e6),
                    pos_z=int(waypoint.z * 1e6),
                )
                for waypoint in waypoints.waypoints
            ],
        )
    api.controller.dotbots[address].waypoints = waypoints_list
    api.controller.dotbots[address].waypoints_threshold = waypoints.threshold
    api.controller.send_payload(int(address, 16), payload)
    await api.controller.notify_clients(
        DotBotNotificationModel(cmd=DotBotNotificationCommand.RELOAD)
    )


@api.delete(
    path="/controller/dotbots/{address}/positions",
    summary="Clear the history of positions of a DotBot",
    tags=["dotbots"],
)
async def dotbot_positions_history_clear(address: str):
    """Clear the history of positions of a dotbot."""
    if address not in api.controller.dotbots:
        raise HTTPException(status_code=404, detail="No matching dotbot found")
    api.controller.dotbots[address].position_history = []


@api.get(
    path="/controller/dotbots/{address}",
    response_model=DotBotModel,
    response_model_exclude_none=True,
    summary="Return information about a dotbot given its address",
    tags=["dotbots"],
)
async def dotbot(address: str, query: DotBotQueryModel = Depends()):
    """Dotbot HTTP GET handler."""
    if address not in api.controller.dotbots:
        raise HTTPException(status_code=404, detail="No matching dotbot found")
    _dotbot = DotBotModel(**api.controller.dotbots[address].model_dump())
    _dotbot.position_history = _dotbot.position_history[: query.max_positions]
    return _dotbot


@api.get(
    path="/controller/dotbots",
    response_model=List[DotBotModel],
    response_model_exclude_none=True,
    summary="Return the list of available dotbots",
    tags=["dotbots"],
)
async def dotbots(query: DotBotQueryModel = Depends()):
    """Dotbots HTTP GET handler."""
    return api.controller.get_dotbots(query)


@api.websocket("/controller/ws/status")
async def websocket_endpoint(websocket: WebSocket):
    """Websocket server endpoint."""
    await websocket.accept()
    api.controller.websockets.append(websocket)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in api.controller.websockets:
            api.controller.websockets.remove(websocket)


@api.put(
    path="/controller/dotbots/compute_orca_velocity",
    tags=["dotbots"],
)
async def compute_orca_velocity(
    agent: Agent,
    neighbors: List[Agent],
    params: OrcaParams,
) -> Vec2:
    return compute_orca_velocity_for_agent(agent, neighbors, params)


@api.post(
    path="/controller/dotbots/run_test",
)
async def run_test(
    params: OrcaParams,
) -> Vec2:
    query = DotBotQueryModel(
        application=ApplicationType.DotBot,
        status=DotBotStatus.ACTIVE
    )
    dotbots: List[DotBotModel] = api.controller.get_dotbots(query)

    # Define the 
    goals = assign_goals(dotbots)

    bot_radius = 0.02
    dt = 0.10

    while True:
        dotbots: List[DotBotModel] = api.controller.get_dotbots(query)
        agents: List[Agent] = []

        for bot in dotbots:
            agents.append(
                Agent(
                    id = bot.address,
                    position=Vec2(x=bot.lh2_position.x, y=bot.lh2_position.y),
                    velocity=Vec2(x=0, y=0),
                    radius=bot_radius,
                    direction=bot.direction, 
                    max_speed=1.0, # Must match the maxSpeed used in preferred_vel calculation
                    preferred_velocity=preferred_vel(dotbot=bot, goal=goals.get(bot.address)),
                )
            )

        all_done = all(a.preferred_velocity.x == 0 and a.preferred_velocity.y == 0 for a in agents)
        if all_done:
            break
        for agent in agents:
            neighbors = [neighbor for neighbor in agents if neighbor.id != agent.id]


            orca_vel = await compute_orca_velocity(agent, neighbors=neighbors, params=params)
            orca_vel = Vec2(x=orca_vel.x * 0.15, y=orca_vel.y * 0.15)

            waypoints = DotBotWaypoints(threshold=20, waypoints=[DotBotLH2Position(x=agent.position.x + orca_vel.x, y=agent.position.y + orca_vel.y, z=0)])
            # POST waypoint
            await dotbots_waypoints(address=agent.id, application=0, waypoints=waypoints)
        await asyncio.sleep(dt)

    TARGET_DIR = 180
    TOLERANCE = 10  # degrees


    while True:
        all_near_target = True

        dotbots: List[DotBotModel] = api.controller.get_dotbots(query)
        for dotbot in dotbots:
            if abs(dotbot.direction - TARGET_DIR) < TOLERANCE:
                await dotbots_move_raw(address=dotbot.address, application=0, command=DotBotMoveRawCommandModel(left_y=0, right_y=-0, left_x=0, right_x=0))
            else:
                all_near_target = False
                await dotbots_move_raw(address=dotbot.address, application=0, command=DotBotMoveRawCommandModel(left_y=50, right_y=-50, left_x=0, right_x=0))
        if all_near_target:
            break

        await asyncio.sleep(dt)


    return Vec2(x=0, y=0)

def assign_goals(dotbots: List[DotBotModel]) -> Dict[str, dict]:
    """
    Assign goals based on distance to the base goal (0.2, 0.2):
    - Closest bot gets (0.2, 0.2)
    - Next gets (0.2, 0.3)
    - Next gets (0.2, 0.4)
    - etc.
    """

    (base_x, base_y) = (0.2, 0.4)
    spacing = 0.1  # distance between goal rows

    # --- Compute distance of each bot to (base_x, base_y) ---
    bots_with_dist = []
    for bot in dotbots:
        dx = bot.lh2_position.x - base_x
        dy = bot.lh2_position.y - base_y
        dist = (dx*dx + dy*dy) ** 0.5
        bots_with_dist.append((dist, bot))

    # --- Sort by distance ascending ---
    bots_with_dist.sort(key=lambda item: item[0])

    # --- Assign goals in sorted order ---
    goals = {}
    for idx, (_, bot) in enumerate(bots_with_dist):
        goals[bot.address] = {
            "x": base_x,
            "y": base_y + idx * spacing,
        }

    return goals


def preferred_vel(dotbot: DotBotModel, goal: Vec2 | None) -> Vec2:
    if goal is None:
        return Vec2(x=0, y=0)

    dx = goal["x"] - dotbot.lh2_position.x
    dy = goal["y"] - dotbot.lh2_position.y
    dist = math.sqrt(dx*dx + dy*dy)

    # If close to goal, stop
    if dist < 0.02:
        return Vec2(x=0, y=0)

    max_speed = 0.75 if dist >= 0.1 else 0.75 * (dist / 0.1)


    # Right-hand rule bias
    bias_angle = 0.2
    # max_deviation = math.radians(45)
    max_deviation = (45 * math.pi) / 180

    # Convert bot direction into radians
    direction = direction_to_rad(dotbot.direction)
    print(direction)
    print(dotbot.direction)

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
    result = Vec2(x=math.cos(final_angle) * max_speed, y=math.sin(final_angle) * max_speed)
    print(result)
    return result

def direction_to_rad(direction: float) -> float:
    rad = (direction + 90) * math.pi / 180.0
    return math.atan2(math.sin(rad), math.cos(rad))  # normalize to [-π, π]


# Mount static files after all routes are defined
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend", "build")
api.mount("/PyDotBot", StaticFiles(directory=FRONTEND_DIR, html=True), name="PyDotBot")
