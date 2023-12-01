from bale import (
    Bot,
    Message,
    MenuKeyboardMarkup,
    MenuKeyboardButton,
    InputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

import config
from models import User, Discount, DiscountUser, Role, Status
from api import Client


class Command:
    START = "/start"
    CANCEL = "انصراف"
    PROFILE = "موجودی حساب"
    SUBCATEGORY = "ساخت لینک"
    DISCOUNTS = "درخواست کد"


class InlineCommands:
    RETURN = "user:return"
    JOINED = "user:joined"
    DISCOUNT_BUY = "user:discount_buy"

    SEND_DISCOUNT = "panel:send_discount"
    CANCEL_TRANSACTION = "panel:cancel_transaction"


async def wait_message(client: Bot, message: Message):
    def answer(m: Message):
        return m.author == message.author and bool(m.text)

    answer_object = await client.wait_for("message", check=answer)
    if answer_object.content == "/panel" or answer_object.content.startswith("/start"):
        return

    return answer_object


async def wait_callback(client: Bot, callback: CallbackQuery):
    def answer(m: Message):
        return m.author == callback.from_user and bool(m.text)

    answer_object = await client.wait_for("message", check=answer)

    return answer_object


async def start_handler(client: Bot, message: Message, user: User, with_message=True):
    if with_message:
        component = MenuKeyboardMarkup()
        component.add(MenuKeyboardButton(text=Command.PROFILE))
        component.add(MenuKeyboardButton(text=Command.SUBCATEGORY))
        component.add(MenuKeyboardButton(text=Command.DISCOUNTS), row=2)

        remove_message = await message.reply("Loading...", components=component)
        # await remove_message.delete()

        if config.START_TYPE == "image":
            file = open(config.IMAGE_PATH, "rb").read()
            photo = InputFile(file)

            await client.send_photo(
                message.from_user.user_id,
                photo,
                caption="سلام به ربات کد تخفیف خوش آمدید!",
            )
        elif config.START_TYPE == "voice":
            file = open(config.VOICE_PATH, "rb").read()
            voice = InputFile(file)

            await client.send_audio(
                message.from_user.user_id,
                voice,
                caption="سلام به ربات کد تخفیف خوش آمدید!",
            )

    answer_object = await wait_message(client, message)
    return await answer_checker(client, answer_object, user)


async def profile_handler(client: Bot, message: Message, user: User):
    await user.load()
    sub_user_count = await User.objects.filter(from_id=user.user_id).count()
    discount_buy_count = await DiscountUser.objects.filter(user=user).count()
    text = f"""
    ایدی عددی : {user.user_id}
    تعداد زیر مجموعه ها : {sub_user_count}
    موجودی شما : {user.balance}
    تعداد کد های درخواست شده : {discount_buy_count}
    """
    await message.reply(text)
    return await start_handler(client, message, user, with_message=False)


async def subcategory_handler(client: Bot, message: Message, user: User):
    text = f"""
    لینک زیر مجموعه گیری شما:
    {config.BOT_LINK + "?start=" + str(message.from_user.user_id)}
    به ازای هر کاربر جدیدی که با لینک شما عضو ربات شود مبلغ {config.reward} به موجودی شما اضافه میشود! 
    """
    await message.reply(text)
    return await start_handler(client, message, user, with_message=False)


async def discounts_handler(client: Bot, message: Message, user: User):
    component = InlineKeyboardMarkup()
    discounts = await Discount.objects.all()
    if not discounts:
        await message.reply("هنوز هیچ تخفیفی اضافه نشده است!")
        return await start_handler(client, message, user, with_message=False)

    remove_message = await message.reply("Loading...", components=MenuKeyboardMarkup())
    await remove_message.delete()

    for index, discount in enumerate(discounts):
        discount: Discount
        component.add(InlineKeyboardButton(
            discount.name,
            callback_data=InlineCommands.DISCOUNT_BUY + ":" + discount.name,
        ),
            row=index + 1
        )

    component.add(InlineKeyboardButton(
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
            await from_user.update(balance=(from_user.balance + config.reward))
            await client.send_message(from_id, "یک کاربر جدید با لینک شما وارد ربات شد! یک امتیاز به شما "
                                               "اضافه شد")

        return await start_handler(client, callback.message, user)


async def discount_buy_callback(client: Bot, callback: CallbackQuery, user: User):
    await callback.message.delete()
    discount = await Discount.objects.get(name=callback.data.split(":")[2])
    # get price --------------------------------
    component = MenuKeyboardMarkup()
    component.add(MenuKeyboardButton(Command.CANCEL))
    await callback.message.chat.send(
        "لطفا مبلغ کد تخفیف درخواستی را وارد کنید(تومان) برای مثال:\n2000", components=component)

    answer_object = await wait_callback(client, callback)
    if answer_object.content == Command.CANCEL:
        return await answer_checker(client, answer_object, user)

    if not answer_object.content.isdigit():
        await answer_object.reply("مبلغ به درستی وارد نشده است!")
        return await discount_buy_callback(client, callback, user)

    price = int(answer_object.content)

    if price > user.balance:
        component = InlineKeyboardMarkup()
        component.add(InlineKeyboardButton("بازگشت به منوی اصلی", callback_data=InlineCommands.RETURN))
        return await answer_object.reply(
            f"شما موجودی کافی برای انجام این تراکنش را ندارید\n موجودی شما: {user.balance}",
            components=component,
        )

    # get full-name --------------------------------
    component = MenuKeyboardMarkup()
    if user.name:
        component.add(MenuKeyboardButton(user.name))
    component.add(MenuKeyboardButton(Command.CANCEL))
    await answer_object.reply("لطفا نام و نام خانوادگی خود را وارد کنید برای مثال:\nفرهاد غلامی")

    answer_object = await wait_callback(client, callback)

    if answer_object.content == Command.CANCEL:
        return await answer_checker(client, answer_object, user)
    await user.update(name=answer_object.content)
    # get father_name --------------------------------
    component = MenuKeyboardMarkup()
    if user.father_name:
        component.add(MenuKeyboardButton(user.father_name))
    component.add(MenuKeyboardButton(Command.CANCEL))
    await answer_object.reply("لطفا نام و نام خانوادگی و نام پدر خود را وارد کنید برای مثال:\nمحسن غلامی")

    answer_object = await wait_callback(client, callback)

    if answer_object.content == Command.CANCEL:
        return await answer_checker(client, answer_object, user)
    await user.update(father_name=answer_object.content)
    # get national-code --------------------------------
    while True:
        component = MenuKeyboardMarkup()
        if user.national_code:
            component.add(MenuKeyboardButton(str(user.national_code)))
        component.add(MenuKeyboardButton(Command.CANCEL))
        await answer_object.reply("لطفاً کد ملی خود را وارد کنید برای مثال:\n9109109100")

        answer_object = await wait_callback(client, callback)

        if answer_object.content == Command.CANCEL:
            return await answer_checker(client, answer_object, user)
        if answer_object.content.isdigit():
            await user.update(national_code=answer_object.content)
            break
        else:
            await answer_object.reply("کد ملی باید بصورت عدد باشد! لطفا دوباره امتحان کنید!")
    # final part -----------------------------------------
    remove_message = await answer_object.reply("Loading...", components=MenuKeyboardMarkup())
    await remove_message.delete()

    await user.update(balance=(user.balance - price))
    transaction = await DiscountUser.objects.create(
        discount=discount,
        user=user,
        price=price,
        name=user.name,
        father_name=user.father_name,
        national_code=user.national_code,
        status=Status.PENDING,
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
    component = InlineKeyboardMarkup()
    component.add(InlineKeyboardButton(
        "ارسال کد تخفیف", callback_data=InlineCommands.SEND_DISCOUNT + ":" + str(transaction.id)))
    component.add(InlineKeyboardButton(
        "لفو تراکنش!", callback_data=InlineCommands.CANCEL_TRANSACTION + ":" + str(transaction.id)))
    await client.send_message(config.ADMIN, text, components=component)

    component = InlineKeyboardMarkup()
    component.add(InlineKeyboardButton("بازگشت به منوی اصلی", callback_data=InlineCommands.RETURN))
    await answer_object.reply(
        "درخواست شما با موفقیت ثبت شد به زودی کد تخفیف در همین ربات برای شما ارسال خواهد شد ("
        "ممکن است تا ۱۲ ساعت طول بکشد!)",
        components=component,
    )


commands = {
    # < user menu commands >
    Command.CANCEL: start_handler,
    Command.PROFILE: profile_handler,
    Command.SUBCATEGORY: subcategory_handler,
    Command.DISCOUNTS: discounts_handler,
    # < user inline commands >
    InlineCommands.RETURN: return_callback,
    InlineCommands.JOINED: joined_callback,
    InlineCommands.DISCOUNT_BUY: discount_buy_callback,
}


async def answer_checker(client: Bot, message: Message, user: User):
    if not message:
        return

    if message.content.startswith("/start") or message.content == "/panel":
        return
    try:
        return await commands[message.content](client, message, user)
    except KeyError:
        await client.send_message(user.user_id, "دستور یافت نشد!")
        answer_object = await wait_message(client, message)
        return await answer_checker(client, answer_object, user)
    except Exception as e:
        print(e)
        return


async def callback_checker(client: Bot, callback: CallbackQuery, user: User):
    command = ":".join(callback.data.split(':')[:2])
    return await commands[command](client, callback, user)
