import json

class DotBotWsClient:
    def __init__(self, host, port):
        self.url = f"ws://{host}:{port}/controller/ws/dotbots"
        self.ws = None

    async def connect(self):
        import websockets
        self.ws = await websockets.connect(self.url)

    async def close(self):
        await self.ws.close()

    async def send(self, cmd, address, application, data):
        await self.ws.send(json.dumps({
            "cmd": cmd,
            "address": address,
            "application": application,
            "data": data,
        }))
