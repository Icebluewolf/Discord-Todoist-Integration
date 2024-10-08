import re
from datetime import datetime

import discord
from discord.utils import format_dt
from todoist_api_python.models import Task, Label
from initialization import task_cache


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
    "grey": "🩶",
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
            due = datetime.strptime(task.due.datetime.strip("Z"), "%Y-%m-%dT%H:%M:%S")
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


async def get_subtasks_recursive(parent: Task, tasks: list[Task]) -> tuple[dict[str, dict], dict[str, Task]]:
    """
    Recursively find all subtasks given a parent task.
    Returns a table and a reference.
    Table - dict with parent IDs as keys and subtasks in sub-dicts as values
    Reference - dict with keys as task IDs and values of the task object.
    :param parent:
    :param tasks:
    :return:
    """
    children = [t for t in tasks if t.parent_id == parent.id]
    all_children: dict[str, dict] = {}
    linked_children: dict[str, Task] = {}

    for child in children:
        table, reference = await get_subtasks_recursive(child, tasks)
        all_children[child.id] = table
        linked_children[child.id] = child
        linked_children.update(reference)

    return all_children, linked_children


async def format_subtasks(subtasks: dict[str, dict], reference: dict[str, Task], level=0) -> str:
    result = ""
    for t_id, children in subtasks.items():
        result += "  " * level + f"- {"✅ " if reference[t_id].is_completed else ""}{await get_shortened(reference[t_id].content, 50)}\n"
        result += await format_subtasks(children, reference, level=level+1)
    return result


async def get_task_info(task: Task, label_objects: list[Label]) -> discord.Embed:
    due = await get_due_datetime(task)
    title = f"{"✅" if task.is_completed else ""} {await get_shortened(await remove_discord_jump(task.content), 100)}"
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
            f"    {format_dt(due, 'f')}\n"
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

    # Subtasks
    table, linked = await get_subtasks_recursive(task, await task_cache.get_tasks())
    if table:
        e.add_field(name="Subtasks", value=await format_subtasks(table, linked), inline=False)

    return e
