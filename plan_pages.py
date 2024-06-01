from discord.ext import pages
import discord
from utils import get_due_datetime
from datetime import datetime
from todoist_api_python.models import Task, Project


async def create_pages(tasks: list[Task], project_obj: list[Project]) -> pages.Paginator:
    async def create_embed(section_tasks: list[Task]) -> discord.Embed:
        embed = discord.Embed(title="Your Tasks")
        embed.set_footer(text="Last Updated")
        embed.timestamp = datetime.now()

        for task in section_tasks:
            if task.parent_id:
                continue
            v = f"`{task.id}`"
            if due := await get_due_datetime(task):
                v += f" | Due {discord.utils.format_dt(due, 'R')}"
            v += f"\n{task.description}" if task.description else ""
            if subtasks := [st for st in section_tasks if st.parent_id == task.id]:
                v += "\n**Sub-Tasks:**"
                for subtask in subtasks:
                    v += f"\n- {subtask.content} | [{subtask.id}]({subtask.url})"
                    if due := await get_due_datetime(subtask):
                        v += f" | Due {discord.utils.format_dt(due, 'R')}"
            embed.add_field(
                name=(
                    (task.content[:253] + "...")
                    if len(task.content) > 256
                    else task.content
                ),
                value=v,
                inline=False,
            )
        return embed


    # TODO: Make The Sorting And Filtering Of Tasks More Efficient
    annotated_tasks = [
        (await get_due_datetime(t) or datetime.max, t.id, t) for t in tasks
    ]
    annotated_tasks.sort()
    tasks = [t for _, _, t in annotated_tasks]

    # Group The Tasks Into Different Projects
    project_name_map = {project.id: project.name for project in project_obj}
    projects: [str, list[Task]] = {"All": tasks, "Inbox": []}
    for task in tasks:
        if task.project_id:
            projects.setdefault(project_name_map[task.project_id], []).append(task)
        else:
            projects["Inbox"].append(task)

    pgs = []
    for category, tasks in projects.items():
        pgs.append(pages.PageGroup(label=category, pages=[await create_embed(tasks[i:i + 10]) for i in range(0,
                                                                                                        len(tasks), 10
                                                                                                       )]))

    return pages.Paginator(pages=pgs, show_menu=True, menu_placeholder="Project")
