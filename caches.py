import asyncio
from datetime import datetime, timedelta

from todoist_api_python.models import Label
from todoist_api_python.api_async import TodoistAPIAsync


class TaskAutocompleteCooldown:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.last_executed = {}
        self.cache = {}
        self.lock = asyncio.Lock()

    async def can_execute(self, user_id: int) -> bool:
        async with self.lock:
            last_time = self.last_executed.get(user_id, datetime.min)
            current_time = datetime.now()
            if current_time - last_time >= timedelta(seconds=self.seconds):
                self.last_executed[user_id] = current_time
                return True
            return False

    async def set_cache(self, user_id: int, tasks: list) -> None:
        async with self.lock:
            self.cache[user_id] = tasks

    async def get_cache(self, user_id: int) -> list:
        async with self.lock:
            return self.cache[user_id]


class LabelsCache:
    def __init__(self, seconds: int, api: TodoistAPIAsync) -> None:
        self.seconds = seconds
        self.last_executed = {}
        self.lock = asyncio.Lock()
        self.labels = None
        self.api = api

    async def can_execute(self, user_id: int) -> bool:
        async with self.lock:
            last_time = self.last_executed.get(user_id, datetime.min)
            current_time = datetime.now()
            if current_time - last_time >= timedelta(seconds=self.seconds):
                self.last_executed[user_id] = current_time
                return True
            return False

    async def get_labels(self, user_id: int) -> list[Label]:
        if await self.can_execute(user_id):
            self.labels = await self.api.get_labels()
        return self.labels
