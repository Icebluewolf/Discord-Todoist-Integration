import asyncio

import discord
import os
from datetime import datetime

from discord import Interaction
from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Task
from utils import get_due_datetime, get_task_info
from cooldowns import TaskAutocompleteCooldown

bot = discord.Bot()
api = TodoistAPIAsync(os.getenv('todoist_token'))


class AddTaskOptions(discord.ui.View):
    def __init__(self, task: Task, **kwargs):
        super().__init__(**kwargs)
        self.task = task
        self.add_item(CompleteTask(task))

    @discord.ui.button(label="Add Info", style=discord.ButtonStyle.blurple)
    async def add_desc(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(AddDesc(self.task, self))

    async def create_embed(self):
        task_name = self.task.content if len(self.task.content) < 256 else (self.task.content[:253] + "...")
        due = await get_due_datetime(self.task)
        embed = discord.Embed(
            description=f"**{task_name}**\n`{self.task.id}`"
                        f"{(' | Due: ' + discord.utils.format_dt(due, 'R')) if due else ''}\n\n{self.task.description}",
            color=56908,
            timestamp=due,
            url=self.task.url
        )
        embed.set_author(name="Task Created")
        embed.set_footer(text="Due Date" if due else None)
        return embed


class AddDesc(discord.ui.Modal):
    def __init__(self, task: Task, view: AddTaskOptions):
        super().__init__(title="Set Additional Info")
        self.add_item(discord.ui.InputText(label="Enter Description", required=False, value=task.description))
        self.add_item(discord.ui.InputText(label="Enter Due Date", required=False, placeholder="IE: tomorrow at "
                                                                                               "12:00",
                                           value=task.due.string if task.due else None))
        self.add_item(discord.ui.InputText(label="Priority", required=False,
                                           placeholder="Must Be A Number. 1: CRITICAL | 2: HIGH | 3: MEDIUM | 4: LOW"))
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
                priority = 1
        except ValueError:
            priority = 1
        else:
            # Reverse The Priority As The API Accepts 1 As Low Where The UI Shows 1 As High
            priority = [4, 3, 2, 1][priority-1]

        response = await api.update_task(task_id=self.task.id, description=self.children[0].value.strip(),
                                         due_string=due_string, priority=priority)
        response = Task.from_dict(response)
        self.task.description = self.children[0].value.strip()
        self.task.due = response.due
        self.task.priority = priority
        await interaction.followup.edit_message(self.parent_view.message.id, embed=await
        self.parent_view.create_embed())


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
    annotated_tasks = [(await get_due_datetime(t) or datetime.max, t.id, t) for t in tasks]
    annotated_tasks.sort()
    tasks = [t for key, ukey, t in annotated_tasks]
    for task in tasks[:min(25, len(tasks))]:
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
        embed.add_field(name=(task.content[:253] + "...") if len(task.content) > 256 else task.content, value=v,
                        inline=False)
    await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(
    integration_types={discord.IntegrationType.user_install},
)
async def todo(ctx: discord.ApplicationContext, task: discord.Option(str, description="The Task To Complete")):
    await ctx.defer()
    try:
        response = await api.add_task(content=task)
        view = AddTaskOptions(response)
        await ctx.respond(embed=await view.create_embed(), view=view, ephemeral=True)
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
    await ctx.defer()
    try:
        response = await api.add_task(content=short_msg)
        view = AddTaskOptions(response)
        await ctx.respond(embed=await view.create_embed(), view=view, ephemeral=True)
    except Exception as error:
        await ctx.respond(error, ephemeral=True)


task_autocomplete_cooldown = TaskAutocompleteCooldown(seconds=15)


async def tasks_autocomplete(ctx: discord.AutocompleteContext):
    if await task_autocomplete_cooldown.can_execute(ctx.interaction.user.id):
        tasks = await api.get_tasks()
        await task_autocomplete_cooldown.set_cache(ctx.interaction.user.id, tasks)
    else:
        tasks = await task_autocomplete_cooldown.get_cache(ctx.interaction.user.id)
    task_names = [discord.OptionChoice(task.content, task.id) for task in tasks
                  if task.content.lower().startswith(ctx.value.lower())]
    return task_names[0:min(25, len(task_names))]


@bot.slash_command(
    integration_types={discord.IntegrationType.user_install}
)
async def view_task(ctx: discord.ApplicationContext, task: discord.Option(str, description="The Task To View",
                                                                          autocomplete=tasks_autocomplete)):
    response = None
    if task.isdigit():
        response = await api.get_task(task)
    elif response is None:
        response = await api.get_tasks(label=task)
        response = response[0]

    if response is None:
        return await ctx.respond("No Tasks Found", ephemeral=True)

    await ctx.respond(embed=await get_task_info(response), view=AddTaskOptions(response), ephemeral=True)


@bot.listen(name="on_ready", once=True)
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print(bot.commands)


bot.run(os.environ["bot_token"])
