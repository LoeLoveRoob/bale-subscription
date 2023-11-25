from bale import (
    Bot,
    Message,
    Components,
    MenuKeyboard,
    RemoveMenuKeyboard,
    InlineKeyboard,
    CallbackQuery, InputFile,
)
from models import User, Discount, Role, DiscountUser
import config

step = None


class Command:
    PANEL = "/panel"
    DISCOUNTS = "تخفیف ها"
    DATABASE = "استخراج دیتابیس"
    CANCEL = "انصراف"


class InlineCommands:
    RETURN = "panel:return"
    DISCOUNT_INFO = "panel:discount_info"
    ADD_DISCOUNT = "panel:add_discount"
    SEND_DISCOUNT = "panel:send_discount"
    CANCEL_TRANSACTION = "panel:cancel_transaction"


async def panel_handler(client: Bot, message: Message, user: User = None):
    if not user:
        user, created = await User.objects.get_or_create(
            defaults={"role": Role.ADMIN, "point": 999999999999},
            user_id=config.ADMIN
        )
    component = Components()
    component.add_menu_keyboard(MenuKeyboard(Command.DISCOUNTS))
    component.add_menu_keyboard(MenuKeyboard(Command.DATABASE))
    await message.reply(
        "سلام ادمین گرامی به پنل مدیریت ربات خوش امدید!", components=component)
    while True:
        answer_object = await client.wait_for("message")
        if answer_object.from_user.user_id == message.from_user.user_id:
            break
    return await answer_checker(client, answer_object, user)


async def discounts_handler(client: Bot, message: Message, user: User):
    remove_object = await message.reply("Loading...", components=RemoveMenuKeyboard())
    await remove_object.delete()

    component = Components()
    discounts = await Discount.objects.all()
    if not discounts:
        component.add_inline_keyboard(InlineKeyboard("اضافه کردن", callback_data=InlineCommands.ADD_DISCOUNT))
        return await message.reply("هنوز هیچ تخفیفی اضافه نشده است!", components=component)

    for index, discount in enumerate(discounts):
        discount: Discount
        component.add_inline_keyboard(InlineKeyboard(
            discount.name,
            callback_data=InlineCommands.DISCOUNT_INFO + ":" + discount.name,
        ),
            row=index + 1
        )

    component.add_inline_keyboard(InlineKeyboard(
        "اضافه کردن",
        callback_data=InlineCommands.ADD_DISCOUNT
    ),
        row=index + 2
    )
    component.add_inline_keyboard(InlineKeyboard(
        "بازگشت به منوی اصلی",
        callback_data=InlineCommands.RETURN
    ),
        row=index + 3
    )
    return await message.reply("لبست تمامی تخفیف ها:", components=component)


async def database_handler(client: Bot, message: Message, user: User):
    database = open("database.sqlite", "rb").read()
    attachment = InputFile(database)
    await message.reply_document(attachment, caption="دیتابیس sqlite میتوانید با استفاده از :\nhttps://www.rebasedata.com/convert-sqlite-to-excel-online\nدیتابیس را به فایل اکسل تبدیل کنید!")
    return await panel_handler(client, message, user)

# < CALLBACKS > --------------------------------

async def return_callback(client: Bot, callback: CallbackQuery, user: User):
    await callback.message.delete()

    return await panel_handler(client, callback.message, user)


async def discount_info_callback(client: Bot, callback: CallbackQuery, user: User):
    await callback.message.delete()

    discount_name = callback.data.split(':')[2]
    discount = await Discount.objects.get(name=discount_name)
    discount_count = await DiscountUser.objects.filter(discount_id=discount.id).count()
    component = Components()
    component.add_inline_keyboard(InlineKeyboard(f"id : {discount.id}"))
    component.add_inline_keyboard(InlineKeyboard(f"name : {discount.name}"), row=2)
    component.add_inline_keyboard(InlineKeyboard(f"buy count : {discount_count}"), row=3)
    component.add_inline_keyboard(InlineKeyboard("بازگشت به منوی اصلی", callback_data=InlineCommands.RETURN), row=4)
    await callback.message.chat.send(f"مشخصات تخفیف {discount.name} به صورت زیر میباشد:", components=component)


async def add_discount_callback(client: Bot, callback: CallbackQuery, user: User):
    message = callback.message
    await callback.message.delete()
    component = Components()
    component.add_menu_keyboard(MenuKeyboard(Command.CANCEL))
    await message.chat.send("لطفا نام کد تخفیف را وارد کنید: ", components=component)
    while True:
        answer_object = await client.wait_for("message")
        if answer_object.from_user.user_id == message.from_user.user_id:
            break
    if answer_object.content == Command.CANCEL:
        return await answer_checker(client, answer_object, user)

    discount, created = await Discount.objects.get_or_create(defaults=dict(
        name=answer_object.content
    ),
        name=answer_object.content
    )
    if created:
        await message.chat.send("کد تخفیف با موفقیت ایجاد شد!")
    else:
        await message.chat.send("کد تخفیف قبلا اضافه شده!")

    return await discounts_handler(client, message, user)


async def send_discount_callback(client: Bot, callback: CallbackQuery, user: User):
    global step
    step = InlineCommands.SEND_DISCOUNT

    transaction = await DiscountUser.objects.get(id=callback.data.split(":")[2])
    await transaction.user.load()
    await transaction.discount.load()
    component = Components()
    component.add_inline_keyboard(InlineKeyboard("انصراف", callback_data=InlineCommands.RETURN))
    ask_object = await callback.message.reply("لطفا کد تحفیف را وارد کتید:", components=component)
    while True:
        answer_object = await client.wait_for("message")
        if answer_object.from_user.user_id == callback.from_user.user_id:
            break
    await ask_object.delete()
    await transaction.update(code=answer_object.content)
    component = Components()
    component.add_inline_keyboard(InlineKeyboard("کد ارسال شده!"))
    await callback.message.edit(callback.message.content, components=component)

    text = f"""
    تراکنش با موفقیت انجام شد!
    مبلغ: {transaction.price}
    نوع کد: {transaction.discount.name}
    کد: {transaction.code}
    """
    step = None
    await client.send_message(transaction.user.user_id, text)
    await answer_object.reply("کد با موفقیت برای کاربر ارسال شد!")
    return await panel_handler(client, callback.message, user)


async def cancel_transaction_callback(client: Bot, callback: CallbackQuery, user: User):
    transaction = await DiscountUser.objects.get(id=callback.data.split(":")[2])
    await transaction.user.load()
    await transaction.discount.load()
    customer = transaction.user
    discount = transaction.discount

    component = Components()
    component.add_menu_keyboard(MenuKeyboard("بله"))
    component.add_menu_keyboard(MenuKeyboard("خیر"))
    ask_object = await callback.message.reply("ایا از حذف تراکنش اطمینان دارید؟", components=component)
    while True:
        answer_object = await client.wait_for("message")
        if answer_object.from_user.user_id == callback.from_user.user_id:
            break
    await ask_object.delete()

    if answer_object.content == "بله":
        await customer.update(point=customer.point + int(transaction.price / config.reward))
        text = f"""
        تراکنش با ایدی {transaction.id} از طرف مدیریت لفو شد!
         مبلغ به حساب کاربری شما بازگشت خورد!
        """
        await client.send_message(customer.user_id, text)
        component = Components()
        component.add_inline_keyboard(InlineKeyboard("تراکنش لغو شده!"))
        await callback.message.edit(callback.message.content, components=component)
        await answer_object.reply("تراکنش با موفقیت لغو شد!")
        return panel_handler(client, callback.message, user)
    elif answer_object.content == "خیر":
        return await panel_handler(client, callback.message, user)
    else:
        await answer_object.reply("دستور نا معتبر لطفا دوباره امتحان کنید!")
        return await cancel_transaction_callback(client, callback, user)


commands = {
    # < admin menu commands >
    Command.CANCEL: panel_handler,
    Command.DISCOUNTS: discounts_handler,
    Command.DATABASE: database_handler,
    # < admin inline commands >
    InlineCommands.RETURN: return_callback,
    InlineCommands.DISCOUNT_INFO: discount_info_callback,
    InlineCommands.ADD_DISCOUNT: add_discount_callback,
    InlineCommands.SEND_DISCOUNT: send_discount_callback,
    InlineCommands.CANCEL_TRANSACTION: cancel_transaction_callback,
}


async def answer_checker(client: Bot, message: Message, user: User):
    if message.content.startswith("/start"):
        return
    try:
        return await commands[message.content](client, message, user)
    except:
        if step == InlineCommands.SEND_DISCOUNT:
            return
        await client.send_message(user.user_id, "دستور یافت نشد!")
        while True:
            answer_object = await client.wait_for("message")
            if answer_object.from_user.user_id == message.from_user.user_id:
                break
        return await answer_checker(client, answer_object, user)


async def callback_checker(client: Bot, callback: CallbackQuery, user: User):
    # to cut the extra arguments
    command = ":".join(callback.data.split(':')[:2])
    return await commands[command](client, callback, user)
