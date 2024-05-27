import asyncio
from datetime import datetime, timedelta


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
