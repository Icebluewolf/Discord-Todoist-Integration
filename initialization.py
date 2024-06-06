import discord
import os
from todoist_api_python.api_async import TodoistAPIAsync
from caches import LabelsCache, TaskAutocompleteCooldown, TaskCache

bot = discord.Bot()
api = TodoistAPIAsync(os.getenv("todoist_token"))

label_cache = LabelsCache(60, api)
task_autocomplete_cooldown = TaskAutocompleteCooldown(seconds=15)
task_cache = TaskCache(15, api)
