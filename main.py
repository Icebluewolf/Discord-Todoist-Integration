import asyncio

import discord
import os
from datetime import datetime

from discord import Interaction
from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Task, Label
from utils import get_due_datetime, get_task_info, LABEL_EMOJIS
from caches import TaskAutocompleteCooldown, LabelsCache

bot = discord.Bot()
api = TodoistAPIAsync(os.getenv("todoist_token"))

label_cache = LabelsCache(60, api)


class AddTaskOptions(discord.ui.View):
    def __init__(self, task: Task, labels: list[Label], parents: list[str] | None = None):
        super().__init__(timeout=300, disable_on_timeout=True)
        self.task = task
        self.parents = parents or []
        self.add_item(CompleteTask(task))
        self.add_item(TaskLabeler(labels, task))

        if len(self.parents) == 4:
            self.children[1].disabled = True

    @discord.ui.button(label="Add Info", style=discord.ButtonStyle.blurple)
    async def add_desc(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.send_modal(AddDesc(self.task, self))

    @discord.ui.button(label="Add Sub-Task", style=discord.ButtonStyle.green)
    async def add_subtask(self, button: discord.ui.Button, interaction: discord.Interaction):
        modal = discord.ui.Modal(discord.ui.InputText(label="Task"), title="Add Sub-Task")

        async def callback(modal_interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            response = await api.add_task(modal.children[0].value, parent_id=self.task.id)
            parents = self.parents.copy()
            parents.append(self.task.id)
            view = AddTaskOptions(response, await api.get_labels(), parents=parents)
            await modal_interaction.respond(embed=await get_task_info(response, await label_cache.get_labels(
                modal_interaction.user.id)), view=view, ephemeral=True)

        modal.callback = callback
        await interaction.response.send_modal(modal)



class AddDesc(discord.ui.Modal):
    def __init__(self, task: Task, view: AddTaskOptions):
        super().__init__(title="Set Additional Info", timeout=600)
        self.add_item(
            discord.ui.InputText(
                label="Enter Description", required=False, value=task.description, style=discord.InputTextStyle.long
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Enter Due Date",
                required=False,
                placeholder="IE: tomorrow at " "12:00",
                value=task.due.string if task.due else None,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Priority",
                required=False,
                placeholder="Must Be A Number. 1: CRITICAL | 2: HIGH | 3: MEDIUM | 4: LOW",
                value=str([4, 3, 2, 1][task.priority - 1])
            )
        )
        self.add_item(discord.ui.InputText(label="Labels", required=False, placeholder="Comma Separated List Of "
                                                                                       "Labels", value=", "
                                                                                                       "".join(task.labels)))
        self.task = task
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.children[1].value.strip():
            due_string = self.children[1].value.strip()
        else:
            due_string = "no due date"

        try:
            priority = int(self.children[2].value)
            if priority <= 0 or 5 <= priority:
                priority = 4
        except ValueError:
            priority = 4
        self.task.priority = priority
        # Reverse The Priority As The API Accepts 1 As Low Where The UI Shows 1 As High
        priority = [4, 3, 2, 1][priority - 1]

        labels = [x.strip() for x in self.children[3].value.split(",")]

        response = await api.update_task(
            task_id=self.task.id,
            description=self.children[0].value.strip(),
            due_string=due_string,
            priority=priority,
            labels=labels
        )
        response = Task.from_dict(response)
        self.task.description = self.children[0].value.strip()
        self.task.due = response.due
        self.task.priority = priority
        self.task.labels = labels
        await interaction.followup.edit_message(
            self.parent_view.message.id, embed=await get_task_info(self.task, await label_cache.get_labels(
                interaction.user.id))
        )


class CompleteTask(discord.ui.Button):
    def __init__(self, task: Task):
        self.want_completed = False
        self.completed = False
        self.task = task
        self.future = None
        super().__init__(label="Complete", emoji="✅", style=discord.ButtonStyle.green)

    async def mark_as_complete(self):
        if self.completed:
            return
        await asyncio.sleep(5)
        await api.close_task(self.task.id)
        self.completed = True

    async def mark_as_uncomplete(self):
        if not self.completed:
            return
        await asyncio.sleep(5)
        await api.reopen_task(self.task.id)
        self.completed = False

    async def callback(self, interaction: Interaction):
        if self.future:
            self.future.cancel()

        if self.want_completed:
            self.label = "Complete"
            self.emoji = "✅"
            self.style = discord.ButtonStyle.green
            await interaction.edit(view=self.view)
            self.want_completed = False
            self.future = asyncio.ensure_future(self.mark_as_uncomplete())
        else:
            self.label = "Un-Complete"
            self.emoji = "↩"
            self.style = discord.ButtonStyle.red
            await interaction.edit(view=self.view)
            self.want_completed = True
            self.future = asyncio.ensure_future(self.mark_as_complete())


class TaskLabeler(discord.ui.Select):
    def __init__(self, labels: list[Label], task: Task):
        self.task = task
        self.labels = labels

        # Label Priority: Only 25 Can Be Shown
        # Current Labels -> Favorite Labels -> Other Labels
        shown_labels = [label for label in labels if label.name in task.labels]
        # Indicate That It Should Already Be Selected
        for label in shown_labels:
            label.current_task = True
        if len(shown_labels) < 25:
            for label in labels:
                if label not in shown_labels and label.is_favorite:
                    label.current_task = False
                    shown_labels.append(label)
        if len(shown_labels) < 25:
            for label in labels:
                if label not in shown_labels:
                    label.current_task = False
                    shown_labels.append(label)
        shown_labels = shown_labels[: min(25, len(shown_labels))]
        shown_labels = [
            discord.SelectOption(
                label=label.name,
                emoji=LABEL_EMOJIS[label.color],
                default=label.current_task,
            )
            for label in shown_labels
        ]
        super().__init__(max_values=len(shown_labels), options=shown_labels, placeholder="Select Labels")

    async def callback(self, interaction: discord.Interaction):
        await api.update_task(self.task.id, labels=self.values)
        for option in self.options:
            if option.label in self.values:
                option.default = True
            else:
                option.default = False
        self.task.labels = self.values
        await interaction.response.edit_message(embed=await get_task_info(self.task, await label_cache.get_labels(
            interaction.user.id)),
                                                view=self.view)


@bot.slash_command(
    integration_types={discord.IntegrationType.user_install},
)
async def update(ctx: discord.ApplicationContext):
    await ctx.defer()
    tasks = await api.get_tasks()
    embed = discord.Embed(title="Your Tasks")
    embed.set_footer(text="Last Updated")
    embed.timestamp = datetime.now()
    # TODO: Make The Sorting And Filtering Of Tasks More Efficient
    annotated_tasks = [
        (await get_due_datetime(t) or datetime.max, t.id, t) for t in tasks
    ]
    annotated_tasks.sort()
    tasks = [t for key, ukey, t in annotated_tasks]
    for task in tasks[: min(25, len(tasks))]:
        if task.parent_id:
            continue
        v = f"`{task.id}`"
        if due := await get_due_datetime(task):
            v += f" | Due {discord.utils.format_dt(due, 'R')}"
        v += f"\n{task.description}"
        if subtasks := [st for st in tasks if st.parent_id == task.id]:
            v += "\n\n**Sub-Tasks:**"
            for subtask in subtasks:
                v += f"\n- {subtask.content} | `[{subtask.id}]({subtask.url})"
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
    await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(
    integration_types={discord.IntegrationType.user_install},
)
async def todo(
    ctx: discord.ApplicationContext,
    task: discord.Option(str, description="The Task To Complete"),
):
    await ctx.defer(ephemeral=True)
    try:
        response = await api.add_task(content=task)
        view = AddTaskOptions(response, await api.get_labels())
        await ctx.respond(
            embed=await get_task_info(response, await label_cache.get_labels(ctx.author.id)), view=view, ephemeral=True
        )
    except Exception as error:
        await ctx.respond(error, ephemeral=True)


@bot.message_command(
    integration_types={discord.IntegrationType.user_install},
    name="Mark As ToDo",
)
async def mark_as_todo(ctx: discord.ApplicationContext, message: discord.Message):
    short_msg = ""
    if message.content:
        if len(message.content) >= 100:
            short_msg = message.content[:97] + "..."
        else:
            short_msg = message.content
        short_msg += " | "
    # This Link Should Work For All Discord Messages On All Devices But It Is Not Guaranteed
    # TODO: The Jump URL Is Broken In The Current Dev Version Of Pycord
    short_msg += f"[Discord Jump]({message.jump_url})"
    await ctx.defer(ephemeral=True)
    try:
        response = await api.add_task(content=short_msg)
        view = AddTaskOptions(response, await api.get_labels())
        await ctx.respond(
            embed=await get_task_info(response, await label_cache.get_labels(ctx.author.id)), view=view, ephemeral=True
        )
    except Exception as error:
        await ctx.respond(error, ephemeral=True)


task_autocomplete_cooldown = TaskAutocompleteCooldown(seconds=15)


async def tasks_autocomplete(ctx: discord.AutocompleteContext):
    if await task_autocomplete_cooldown.can_execute(ctx.interaction.user.id):
        tasks = await api.get_tasks()
        await task_autocomplete_cooldown.set_cache(ctx.interaction.user.id, tasks)
    else:
        tasks = await task_autocomplete_cooldown.get_cache(ctx.interaction.user.id)
    task_names = [
        discord.OptionChoice(task.content, task.id)
        for task in tasks
        if task.content.lower().startswith(ctx.value.lower())
    ]
    return task_names[0 : min(25, len(task_names))]


@bot.slash_command(integration_types={discord.IntegrationType.user_install})
async def view_task(
    ctx: discord.ApplicationContext,
    task: discord.Option(
        str, description="The Task To View", autocomplete=tasks_autocomplete
    ),
):
    response = None
    if task.isdigit():
        response = await api.get_task(task)
    elif response is None:
        response = await api.get_tasks(label=task)
        response = response[0]

    if response is None:
        return await ctx.respond("No Tasks Found", ephemeral=True)

    await ctx.respond(
        embed=await get_task_info(response, await label_cache.get_labels(ctx.author.id)),
        view=AddTaskOptions(response, await api.get_labels()),
        ephemeral=True,
    )


@bot.listen(name="on_ready", once=True)
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print(bot.commands)


bot.run(os.environ["bot_token"])
