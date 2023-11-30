import os
import sys

from bale import (
    Bot,
    Message,
    MenuKeyboardMarkup,
    MenuKeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyMarkupItem,
    CallbackQuery,
)
import config
import models
import users
import admin
from models import Role
from api import Client

# sys.path.append(os.path.dirname(__file__))

app = Bot(token=config.TOKEN)


@app.event
async def on_ready():
    if os.path.exists("database.sqlite"):
        all_users = await models.User.objects.all()
        for user in all_users:
            remove_message = await app.send_message(
                user.user_id,
                "Loading...",
                components=MenuKeyboardMarkup()
            )
            await remove_message.delete()

            component = MenuKeyboardMarkup()
            component.add(MenuKeyboardButton("/start"))
            message = await app.send_message(
                user.user_id,
                "ربات ریستارت شد! لطفا دوباره با استفاده از منو پایین استارت کنید!",
                components=component
            )


@app.event
async def on_message(message: Message):
    if message.chat.type != "private" or not message.content:
        return
    await models.main()
    api = Client(app)

    text = message.content
    user_id = message.from_user.user_id
    # ADMIN ------------------------------
    if user_id == config.ADMIN:
        user, created = await models.User.objects.get_or_create(
            defaults={"role": Role.ADMIN, "balance": 999999999999},
            user_id=config.ADMIN
        )
        if text == admin.Command.PANEL:
            return await admin.panel_handler(app, message, user)
        elif text == users.Command.START:
            return await users.start_handler(app, message, user)

    # USER -------------------------------
    channel = await api.get_chat(config.CHANNEL)
    chat_member = await api.get_chat_member(channel.chat_id, user_id)

    if await models.User.objects.filter(user_id=user_id).exists():
        user = await models.User.objects.get(user_id=user_id)
        if not chat_member:
            component = InlineKeyboardMarkup()
            component.add(InlineKeyboardButton(
                text="عضو شدم", callback_data=users.InlineCommands.JOINED))
            return await message.reply(f"لطفا برای استفاده از ربات اول در کانال ما (@{channel.username}) عضو شوید",
                                       components=component)
    else:
        if message.content.startswith(users.Command.START):
            if len(message.content.split()) > 1:
                from_id = message.content.split()[1]

                if not chat_member:
                    await models.User.objects.create(
                        user_id=user_id,
                        role=Role.USER,
                    )
                    component = InlineKeyboardMarkup()
                    component.add(InlineKeyboardButton(
                        text="عضو شدم", callback_data=users.InlineCommands.JOINED + ":" + from_id))
                    return await message.reply(f"لطفا برای استفاده از ربات اول در کانال ما (@{channel.username}) عضو شوید",
                                               components=component)

                # check if the from id valid and from_id exists!
                if not from_id.isdigit() or not await models.User.objects.filter(user_id=from_id).exists():
                    return await message.reply("لینک معرف نامعتبر است!")

                from_user = await models.User.objects.get(user_id=from_id)
                user = await models.User.objects.create(
                    from_id=from_id,
                    user_id=user_id,
                    role=Role.USER,
                )
                await from_user.update(balance=(from_user.balance + config.reward))
                await app.send_message(from_user.user_id, "یک کاربر جدید با لینک شما وارد ربات شد! یک امتیاز به شما "
                                                "اضافه شد")
            else:
                return await message.reply("لطفا برای استارت ربات از لینک معرف استفاده نمایید")

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
