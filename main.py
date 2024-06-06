import discord
import os
from utils import get_task_info, get_subtasks_recursive
from plan_pages import create_pages
from views import AddTaskOptions
from initialization import bot, api, label_cache, task_autocomplete_cooldown, task_cache


@bot.slash_command(
    integration_types={discord.IntegrationType.user_install},
    description="View Upcoming Tasks",
)
async def plan(ctx: discord.ApplicationContext):
    await ctx.defer()
    tasks = await api.get_tasks()
    paginator = await create_pages(tasks, await api.get_projects())
    await paginator.respond(interaction=ctx.interaction, ephemeral=True)


@bot.slash_command(
    integration_types={discord.IntegrationType.user_install},
)
async def todo(
    ctx: discord.ApplicationContext,
    task: discord.Option(str, description="The Task To Complete"),
):
    await ctx.defer(ephemeral=True)
    response = await api.add_task(content=task)
    view = AddTaskOptions(response, await api.get_labels())
    await ctx.respond(
        embed=await get_task_info(
            response, await label_cache.get_labels(ctx.author.id)
        ),
        view=view,
        ephemeral=True,
    )


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
            embed=await get_task_info(
                response, await label_cache.get_labels(ctx.author.id)
            ),
            view=view,
            ephemeral=True,
        )
    except Exception as error:
        await ctx.respond(error, ephemeral=True)


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
    return task_names[0: min(25, len(task_names))]


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
        embed=await get_task_info(
            response, await label_cache.get_labels(ctx.author.id)
        ),
        view=AddTaskOptions(response, await api.get_labels(), subtasks=await get_subtasks_recursive(response,
                                                                                            await task_cache.get_tasks(

                                                                                            ))),
        ephemeral=True,
    )


@bot.listen(name="on_ready", once=True)
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print(bot.commands)


bot.run(os.environ["bot_token"])
