from bale import (
    Bot,
    Message,
    Components,
    MenuKeyboard,
    InlineKeyboard,
    RemoveMenuKeyboard,
    CallbackQuery,
)
import config
import models
import users
import admin
from models import Role
from api import Client

app = Bot(token=config.TOKEN)


@app.event
async def on_message(message: Message):
    if message.chat.type != "private":
        return
    await models.main()
    api = Client(app)

    text = message.content
    user_id = message.from_user.user_id
    # ADMIN ------------------------------
    if user_id == config.ADMIN:
        user, created = await models.User.objects.get_or_create(
            defaults={"role": Role.ADMIN, "point": 999999999999},
            user_id=config.ADMIN
        )
        if text == admin.Command.PANEL:
            return await admin.panel_handler(app, message, user)

    # USER -------------------------------
    channel = await api.get_chat(config.CHANNEL)
    chat_member = await api.get_chat_member(channel.chat_id, user_id)

    if await models.User.objects.filter(user_id=user_id).exists():
        user = await models.User.objects.get(user_id=user_id)
        if not chat_member:
            component = Components()
            component.add_inline_keyboard(InlineKeyboard(
                text="عضو شدم", callback_data=users.InlineCommands.JOINED))
            return await message.reply(f"لطفا برای استفاده از ربات اول در کانال ما (@{channel.username}) عضو شوید",
                                       components=component)
    else:
        if message.content.startswith(users.Command.START) and len(message.content.split()) > 1:
            from_id = message.content.split()[1]

            if not chat_member:
                user = await models.User.objects.create(
                    user_id=user_id,
                    role=Role.USER,
                )
                component = Components()
                component.add_inline_keyboard(InlineKeyboard(
                    text="عضو شدم", callback_data=users.InlineCommands.JOINED + ":" + from_id))
                return await message.reply(f"لطفا برای استفاده از ربات اول در کانال ما (@{channel.username}) عضو شوید",
                                           components=component)

            # check if the from id valid and user not exists!
            if from_id.isdigit():
                user = await models.User.objects.create(
                    from_id=from_id,
                    user_id=user_id,
                    role=Role.USER,
                )
                from_user = await models.User.objects.get(user_id=from_id)
                await from_user.update(point=from_user.point + 1)
                await app.send_message(from_id, "یک کاربر جدید با لینک شما وارد ربات شد! یک امتیاز به شما "
                                                       "اضافه شد")
        else:
            user = await models.User.objects.create(
                user_id=user_id,
                role=Role.USER,
            )
            if not chat_member:
                component = Components()
                component.add_inline_keyboard(InlineKeyboard(
                    text="عضو شدم", callback_data=users.InlineCommands.JOINED))
                return await message.reply(f"لطفا برای استفاده از ربات اول در کانال ما (@{channel.username}) عضو شوید",
                                           components=component)

    # < start handler >
    if message.content.startswith(users.Command.START):
        return await users.start_handler(app, message, user)


@app.event
async def on_callback(callback: CallbackQuery):
    callback.message.from_user.user_id = callback.from_user.user_id
    user_id = callback.from_user.user_id
    if await models.User.objects.filter(user_id=user_id).exists():
        user = await models.User.objects.get(user_id=user_id)
    else:
        return

    if callback.data.startswith("panel:"):
        return await admin.callback_checker(app, callback, user)
    elif callback.data.startswith("user:"):
        return await users.callback_checker(app, callback, user)


app.run()
