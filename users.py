from bale import (
    Bot,
    Message,
    Components,
    MenuKeyboard,
    InputFile,
    RemoveMenuKeyboard,
    InlineKeyboard,
    CallbackQuery,
)

import config
from models import User, Discount, DiscountUser, Role
from api import Client


class Command:
    START = "/start"
    CANCEL = "انصراف"
    PROFILE = "موجودی حساب / ساخت لینک"
    DISCOUNTS = "درخواست کد"


class InlineCommands:
    RETURN = "user:return"
    JOINED = "user:joined"
    DISCOUNT_BUY = "user:discount_buy"

    SEND_DISCOUNT = "panel:send_discount"
    CANCEL_TRANSACTION = "panel:cancel_transaction"


async def start_handler(client: Bot, message: Message, user: User, with_message=True):
    if with_message:
        component = Components()
        component.add_menu_keyboard(MenuKeyboard(text=Command.PROFILE))
        component.add_menu_keyboard(MenuKeyboard(text=Command.DISCOUNTS), row=2)

        await client.send_message(
            message.from_user.user_id,
            # photo,
            text="سلام به ربات کد تخفیف خوش آمدید!",
            components=component
        )

    while True:
        answer_object = await client.wait_for("message")
        if answer_object.from_user.user_id == message.from_user.user_id:
            break
    if answer_object.content == "/panel":
        return
    return await answer_checker(client, answer_object, user)


async def profile_handler(client: Bot, message: Message, user: User):
    remove_object = await message.reply("Loading...", components=RemoveMenuKeyboard())
    await remove_object.delete()

    sub_user_count = await User.objects.filter(from_id=user.user_id).count()
    discount_buy_count = await DiscountUser.objects.filter(user=user).count()
    text = f"""
    ایدی عددی : {user.user_id}
    تعداد زیر مجموعه ها : {sub_user_count}
    موجودی شما : {user.point * config.reward}
    تعداد کد های درخواست شده : {discount_buy_count}
    لینک اختصاصی شما جهت زیرمجموعه گیری: 
    {config.BOT_LINK + f"?start={user.user_id}"}
    """
    await message.reply(text)
    return await start_handler(client, message, user, with_message=False)


async def discounts_handler(client: Bot, message: Message, user: User):
    remove_object = await message.reply("Loading...", components=RemoveMenuKeyboard())
    await remove_object.delete()

    component = Components()
    discounts = await Discount.objects.all()
    if not discounts:
        await message.reply("هنوز هیچ تخفیفی اضافه نشده است!")
        return await start_handler(client, message, user, with_message=False)

    for index, discount in enumerate(discounts):
        discount: Discount
        component.add_inline_keyboard(InlineKeyboard(
            discount.name,
            callback_data=InlineCommands.DISCOUNT_BUY + ":" + discount.name,
        ),
            row=index + 1
        )

    component.add_inline_keyboard(InlineKeyboard(
        "بازگشت به منوی اصلی",
        callback_data=InlineCommands.RETURN
    ),
        row=index + 2
    )
    return await message.reply("لبست تمامی تخفیف ها:", components=component)


# CALLBACKS >------------------------------

async def return_callback(client: Bot, callback: CallbackQuery, user: User):
    await callback.message.delete()
    return await start_handler(client, callback.message, user)


async def joined_callback(client: Bot, callback: CallbackQuery, user: User):
    api = Client(client)
    channel = await api.get_chat(config.CHANNEL)
    chat_member = await api.get_chat_member(channel.chat_id, user.user_id)
    if not chat_member:
        return await callback.message.chat.send("شما هنوز عضو کانال نشده اید!")
    else:
        await callback.message.delete()
        if len(callback.data.split(":")) > 2 and not user.from_id:
            from_id = int(callback.data.split(":")[2])
            await user.update(from_id=from_id)
            from_user = await User.objects.get(user_id=from_id)
            await from_user.update(point=from_user.point + 1)
            await client.send_message(from_id, "یک کاربر جدید با لینک شما وارد ربات شد! یک امتیاز به شما "
                                                   "اضافه شد")

        return await start_handler(client, callback.message, user)


async def discount_buy_callback(client: Bot, callback: CallbackQuery, user: User):
    await callback.message.delete()
    discount = await Discount.objects.get(name=callback.data.split(":")[2])
    # get price --------------------------------
    component = Components()
    component.add_menu_keyboard(MenuKeyboard(Command.CANCEL))
    await callback.message.chat.send(
        "لطفا مبلغ کد تخفیف درخواستی را وارد کنید(تومان) برای مثال:\n2000", components=component)

    while True:
        answer_object = await client.wait_for("message")
        if answer_object.from_user.user_id == callback.from_user.user_id:
            break
    if not answer_object.content.isdigit():
        await answer_object.reply("مبلغ به درستی وارد نشده است!")
        return await discount_buy_callback(client, callback, user)

    price = int(answer_object.content)
    user_balance = user.point * config.reward

    if price > user_balance:
        await answer_object.reply(f"شما موجودی کافی برای انجام این تراکنش را ندارید\n موجودی شما: {user_balance}")
        return await start_handler(client, callback.message, user)
    # get full-name --------------------------------
    component = Components()
    if user.name:
        component.add_menu_keyboard(MenuKeyboard(user.name))
    component.add_menu_keyboard(MenuKeyboard(Command.CANCEL))
    await answer_object.reply("لطفا نام و نام خانوادگی خود را وارد کنید برای مثال:\nفرهاد غلامی")
    while True:
        answer_object = await client.wait_for("message")
        if answer_object.from_user.user_id == callback.from_user.user_id:
            break
    if answer_object.content == Command.CANCEL:
        return await answer_checker(client, answer_object, user)
    await user.update(name=answer_object.content)
    # get father_name --------------------------------
    component = Components()
    if user.father_name:
        component.add_menu_keyboard(MenuKeyboard(user.father_name))
    component.add_menu_keyboard(MenuKeyboard(Command.CANCEL))
    await answer_object.reply("لطفا نام و نام خانوادگی و نام پدر خود را وارد کنید برای مثال:\nمحسن غلامی")
    while True:
        answer_object = await client.wait_for("message")
        if answer_object.from_user.user_id == callback.from_user.user_id:
            break
    if answer_object.content == Command.CANCEL:
        return await answer_checker(client, answer_object, user)
    await user.update(father_name=answer_object.content)
    # get national-code --------------------------------
    while True:
        component = Components()
        if user.national_code:
            component.add_menu_keyboard(MenuKeyboard(str(user.national_code)))
        component.add_menu_keyboard(MenuKeyboard(Command.CANCEL))
        await answer_object.reply("لطفاً کد ملی خود را وارد کنید برای مثال:\n9109109100")
        while True:
            answer_object = await client.wait_for("message")
            if answer_object.from_user.user_id == callback.from_user.user_id:
                break
        if answer_object.content == Command.CANCEL:
            return await answer_checker(client, answer_object, user)
        if answer_object.content.isdigit():
            await user.update(national_code=answer_object.content)
            break
        else:
            await answer_object.reply("کد ملی باید بصورت عدد باشد! لطفا دوباره امتحان کنید!")
    # final part -----------------------------------------
    await user.update(point=user.point - int(price / config.reward))
    transaction = await DiscountUser.objects.create(
        discount=discount,
        user=user,
        price=price,
        name=user.name,
        father_name=user.father_name,
        national_code=user.national_code,
    )
    text = f"""
    درخواست کد تخفیف جدیدی بوجود امد!
    کاربر: {user.user_id}
    نام کاربر: {user.name}
    نام پدر: {user.father_name}
    کد ملی: {user.national_code}
    نوع کد تخفیف: {discount.name}
    مبلغ کد: {price}
    """
    component = Components()
    component.add_inline_keyboard(InlineKeyboard(
        "ارسال کد تخفیف", callback_data=InlineCommands.SEND_DISCOUNT + ":" + str(transaction.id)))
    component.add_inline_keyboard(InlineKeyboard(
        "لفو تراکنش!", callback_data=InlineCommands.CANCEL_TRANSACTION + ":" + str(transaction.id)))
    await client.send_message(config.ADMIN, text, components=component)
    await answer_object.reply("درخواست شما با موفقیت ثبت شد به زودی کد تخفیف در همین ربات برای شما ارسال خواهد شد ("
                              "ممکن است تا ۱۲ ساعت طول بکشد!)")
    return await start_handler(client, callback.message, user)


commands = {
    # < user menu commands >
    Command.CANCEL: start_handler,
    Command.PROFILE: profile_handler,
    Command.DISCOUNTS: discounts_handler,
    # < user inline commands >
    InlineCommands.RETURN: return_callback,
    InlineCommands.JOINED: joined_callback,
    InlineCommands.DISCOUNT_BUY: discount_buy_callback,
}


async def answer_checker(client: Bot, message: Message, user: User):
    if message.content.startswith("/start"):
        return
    try:
        return await commands[message.content](client, message, user)
    except:
        await client.send_message(user.user_id, "دستور یافت نشد!")
        while True:
            answer_object = await client.wait_for("message")
            if answer_object.from_user.user_id == message.from_user.user_id:
                break
        return await answer_checker(client, answer_object, user)


async def callback_checker(client: Bot, callback: CallbackQuery, user: User):
    command = ":".join(callback.data.split(':')[:2])
    return await commands[command](client, callback, user)
