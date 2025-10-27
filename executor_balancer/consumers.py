import json
from channels.generic.websocket import AsyncWebsocketConsumer


class NewRequestConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("new_requests", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("new_requests", self.channel_name)

    async def new_request(self, event):
        await self.send(text_data=json.dumps(event))


class DispatchRequestsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("dispatched", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dispatched", self.channel_name)

    async def request_dispatched(self, event):
        await self.send(text_data=json.dumps(event))
