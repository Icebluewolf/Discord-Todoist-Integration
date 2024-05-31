import re
from datetime import datetime

import discord
from discord.utils import format_dt
from todoist_api_python.models import Task, Label


PRIORITY = {
    1: "`⚪` Normal",
    2: "`🔵` Medium",
    3: "`🟡` High",
    4: "`‼️🔴` Urgent",
}

LABEL_EMOJIS = {
    "berry_red": "🍓",
    "red": "🔴",
    "orange": "🟠",
    "yellow": "🟡",
    "olive_green": "🫒",
    "lime_green": "🎾",
    "green": "🟢",
    "mint_green": "🍵",
    "teal": "🪼",
    "sky_blue": "🏙",
    "light_blue": "🩵",
    "blue": "🔵",
    "grape": "🍇",
    "violet": "🟣",
    "lavender": "🪻",
    "magenta": "🩷",
    "salmon": "🦩",
    "charcoal": "⚫",
    "gray": "🩶",
    "taupe": "🟤",
}


async def get_due_datetime(task: Task) -> datetime | None:
    """
    Formats The String Based Date From ToDoist Into A DateTime Object
    If The Due Date Does Not Have A Set Time The End Of The Day Will Be Used

    :param task: The Task Object From ToDoist
    :return: A :class:`datetime.datetime` Object Or None If There Is No Due Date
    """
    due = None
    if task.due:
        if task.due.datetime:
            due = datetime.strptime(task.due.datetime, "%Y-%m-%dT%H:%M:%S")
        elif task.due.date:
            due = datetime.strptime(task.due.date, "%Y-%m-%d")
            # Make It End Of Day
            due = due.replace(hour=23, minute=59, second=59)
        else:
            # I dont think I want to handle this case as it should not happen.
            # Either need to log a warning or do nothing, just not error
            pass
    return due


async def get_shortened(text: str, length: int) -> str:
    if len(text) <= length:
        return text

    return text[: length - 3] + "..."


async def remove_discord_jump(content: str) -> str:
    # Can be more specific if issues arise
    return re.sub(r" \| \[Discord Jump]\(.+\)", "", content)


async def get_label_object(target: str, labels: list[Label]) -> Label:
    for label in labels:
        if label.name == target:
            return label


async def get_task_info(task: Task, label_objects: list[Label]) -> discord.Embed:
    due = await get_due_datetime(task)
    title = await get_shortened(await remove_discord_jump(task.content), 100)
    e = discord.Embed(
        title=title,
        description=f"`{task.id}`\n" + await get_shortened(task.description, 1000),
        timestamp=datetime.now(),
        color=56908,
        url=task.url,
    )
    e.set_footer(text="Last Updated")

    due_display = (
        (
            f"Due {format_dt(due, 'R')} {'Reoccurring' if task.due.is_recurring else ''}\n"
            f"{format_dt(due, 'f')}\n"
        )
        if due
        else ""
    )
    due_display += f"Created: {format_dt(datetime.strptime(task.created_at, '%Y-%m-%dT%H:%M:%S.%fZ'), 'f')}\n"
    e.add_field(name="Dates", value=due_display, inline=False)

    ctgy_display = f"Parent: `{task.parent_id}`\n" if task.parent_id else ""
    ctgy_display += (
        f"Project: `{task.project_id}`\n" if task.project_id else "Project: Inbox\n"
    )
    ctgy_display += f"Section: `{task.section_id}`\n" if task.section_id else ""
    e.add_field(name="Category", value=ctgy_display, inline=False)

    filter_display = PRIORITY[task.priority]
    labels: list[Label | str] = []
    for label in task.labels:
        obj = await get_label_object(label, label_objects)
        if obj:
            labels.append(f"{LABEL_EMOJIS[obj.color]} {obj.name}")
        else:
            labels.append(label)
    if labels:
        filter_display += "\n**Labels:**\n" + " | ".join(labels)
    e.add_field(name="Filters", value=filter_display, inline=False)
    return e
