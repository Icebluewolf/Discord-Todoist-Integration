import discord
import os

from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Task

bot = discord.Bot()
api = TodoistAPIAsync(os.getenv('todoist_token'))


class AddDesc(discord.ui.Modal):
    def __init__(self, task: Task):
        super().__init__(title="Set Description")
        self.add_item(discord.ui.InputText(label="Enter Description", min_length=1))
        self.task = task

    async def callback(self, interaction: discord.Interaction):
        await api.update_task(task_id=self.task.id, description=self.children[0].value.strip())
        self.task.description = self.children[0].value.strip()
        await interaction.response.edit_message(content="edited")


class AddTaskOptions(discord.ui.View):
    def __init__(self, task: Task, **kwargs):
        super().__init__(**kwargs)
        self.task = task

    @discord.ui.button(label="Add Description", style=discord.ButtonStyle.blurple)
    async def add_desc(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(AddDesc(task=self.task))

    async def create_embed(self):
        task_name = self.task.content if len(self.task.content) < 256 else (self.task.content[:253] + "...")
        embed = discord.Embed(
            description=f"{task_name}\n`{self.task.id}`\n{self.task.description}",
            color=56908,
            timestamp=self.task.due,
        )
        embed.set_author(name="Task Created")
        embed.set_footer(text="Due Date")
        return embed


@bot.slash_command(
    integration_types={discord.IntegrationType.user_install},
)
async def update(ctx: discord.ApplicationContext):
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
    short_msg = ((message.content[:min(len(message.content), 100)] + "... ") if message.content else "")
    short_msg += (f"[Discord Jump](https://canary.discord.com/channels/{message.guild.id if message.guild else '@me'}"
                  f"/{message.channel.id}/{message.id})")
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
