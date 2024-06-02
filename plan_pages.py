from discord import Interaction
from discord.ext import pages
import discord
from utils import get_due_datetime, get_task_info
from datetime import datetime
from todoist_api_python.models import Task, Project
from initilization import label_cache
from views import AddTaskOptions


class TaskSelector(discord.ui.Select):
    def __init__(self, tasks: list[Task]):
        self.tasks = {t.id: t for t in tasks}
        options = [
            discord.SelectOption(
                label=t.content[: min(len(t.content), 100)],
                value=t.id,
                description=t.description[: min(len(t.description), 100)],
            )
            for t in tasks
        ]
        super().__init__(placeholder="Select A Task For More Info", options=options)

    async def callback(self, interaction: Interaction):
        task = self.tasks[self.values[0]]
        labels = await label_cache.get_labels(interaction.user.id)
        await interaction.respond(
            embed=await get_task_info(task, labels),
            view=AddTaskOptions(task, labels),
            ephemeral=True,
        )


async def create_pages(
    tasks: list[Task], project_obj: list[Project]
) -> pages.Paginator:
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
        split_pages = [tasks[i: i + 10] for i in range(0, len(tasks), 10)]
        complete_split_pages = []
        for group in split_pages:
            view = discord.ui.View()
            view.add_item(TaskSelector(group))
            complete_split_pages.append(
                pages.Page(embeds=[await create_embed(group)], custom_view=view)
            )
        pgs.append(pages.PageGroup(label=category, pages=complete_split_pages))

    return pages.Paginator(pages=pgs, show_menu=True, menu_placeholder="Project")
