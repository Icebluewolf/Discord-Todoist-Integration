import discord
import os
from datetime import datetime

from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Task

bot = discord.Bot()
api = TodoistAPIAsync(os.getenv('todoist_token'))


class AddTaskOptions(discord.ui.View):
    def __init__(self, task: Task, **kwargs):
        super().__init__(**kwargs)
        self.task = task

    @discord.ui.button(label="Add Info", style=discord.ButtonStyle.blurple)
    async def add_desc(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(AddDesc(self.task, self))

    async def create_embed(self):
        task_name = self.task.content if len(self.task.content) < 256 else (self.task.content[:253] + "...")
        due = None
        if self.task.due:
            if self.task.due.datetime:
                due = datetime.strptime(self.task.due.datetime, "%Y-%m-%dT%H:%M:%S")
            elif self.task.due.date:
                due = datetime.strptime(self.task.due.date, "%Y-%m-%d")
                # Make It End Of Day
                due = due.replace(hour=23, minute=59, second=59)
            else:
                # I dont think I want to handle this case as it should not happen.
                # Either need to log a warning or do nothing, just not error
                pass
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
                                           value=task.due.string))
        self.task = task
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):
        response = await api.update_task(task_id=self.task.id, description=self.children[0].value.strip(),
                                         due_string=self.children[1].value.strip())
        response = Task.from_dict(response)
        self.task.description = self.children[0].value.strip()
        self.task.due = response.due
        await interaction.response.edit_message(embed=await self.parent_view.create_embed())


@bot.slash_command(
    integration_types={discord.IntegrationType.user_install},
)
async def update(ctx: discord.ApplicationContext):
    # Currently Has No Effect
    try:
        projects = await api.get_projects()
        await ctx.respond(projects)
    except Exception as error:
        await ctx.respond(error)


@bot.slash_command(
    integration_types={discord.IntegrationType.user_install},
)
async def todo(ctx: discord.ApplicationContext, task: discord.Option(str, description="The Task To Complete")):
    try:
        response = await api.add_task(content=task)
        view = AddTaskOptions(response)
        await ctx.respond(embed=await view.create_embed(), view=view)
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
    try:
        response = await api.add_task(content=short_msg)
        view = AddTaskOptions(response)
        await ctx.respond(embed=await view.create_embed(), view=view)
    except Exception as error:
        await ctx.respond(error, ephemeral=True)


@bot.listen(name="on_ready", once=True)
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print(bot.commands)


bot.run(os.environ["bot_token"])
