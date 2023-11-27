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
from models import User, Discount, Role, DiscountUser, Status
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


async def panel_handler(client: Bot, message: Message, user: User = None):
    if not user:
        user, created = await User.objects.get_or_create(
            defaults={"role": Role.ADMIN, "balance": 999999999999},
            user_id=config.ADMIN
        )
    component = MenuKeyboardMarkup()
    component.add(MenuKeyboardButton(Command.DISCOUNTS))
    component.add(MenuKeyboardButton(Command.DATABASE))
    await message.reply(
        "سلام ادمین گرامی به پنل مدیریت ربات خوش امدید!", components=component)

    answer_object = await wait_message(client, message)
    return await answer_checker(client, answer_object, user)


async def discounts_handler(client: Bot, message: Message, user: User):
    remove_message = await message.reply("Loading...", components=MenuKeyboardMarkup())
    await remove_message.delete()

    component = InlineKeyboardMarkup()
    discounts = await Discount.objects.all()
    if not discounts:
        component.add(InlineKeyboardButton("اضافه کردن", callback_data=InlineCommands.ADD_DISCOUNT))
        component.add(InlineKeyboardButton("بازگشت به منوی اصلی", callback_data=InlineCommands.RETURN), row=2)
        return await message.reply("هنوز هیچ تخفیفی اضافه نشده است!", components=component)

    for index, discount in enumerate(discounts):
        discount: Discount
        component.add(InlineKeyboardButton(
            discount.name,
            callback_data=InlineCommands.DISCOUNT_INFO + ":" + discount.name,
        ),
            row=index + 1
        )

    component.add(InlineKeyboardButton(
        "اضافه کردن",
        callback_data=InlineCommands.ADD_DISCOUNT
    ),
        row=index + 2
    )
    component.add(InlineKeyboardButton(
        "بازگشت به منوی اصلی",
        callback_data=InlineCommands.RETURN
    ),
        row=index + 3
    )
    return await message.reply("لبست تمامی تخفیف ها:", components=component)


async def database_handler(client: Bot, message: Message, user: User):
    database = open("database.sqlite", "rb").read()
    attachment = InputFile(database)
    await message.reply_document(attachment,
                                 caption="دیتابیس sqlite میتوانید با استفاده از :\nhttps://www.rebasedata.com/convert-sqlite-to-excel-online\nدیتابیس را به فایل اکسل تبدیل کنید!")
    return await panel_handler(client, message, user)


# < CALLBACKS > --------------------------------

async def return_callback(client: Bot, callback: CallbackQuery, user: User):
    await callback.message.delete()

    return await panel_handler(client, callback.message, user)


async def discount_info_callback(client: Bot, callback: CallbackQuery, user: User):
    await callback.message.delete()

    discount_name = callback.data.split(':')[2]
    discount = await Discount.objects.get(name=discount_name)
    discount_count = await DiscountUser.objects.filter(discount=discount).count()
    component = InlineKeyboardMarkup()
    component.add(InlineKeyboardButton(f"id : {discount.id}"))
    component.add(InlineKeyboardButton(f"name : {discount.name}"), row=2)
    component.add(InlineKeyboardButton(f"buy count : {discount_count}"), row=3)
    component.add(InlineKeyboardButton("بازگشت به منوی اصلی", callback_data=InlineCommands.RETURN), row=4)
    await callback.message.chat.send(f"مشخصات تخفیف {discount.name} به صورت زیر میباشد:", components=component)


async def add_discount_callback(client: Bot, callback: CallbackQuery, user: User):
    message = callback.message
    await callback.message.delete()
    component = MenuKeyboardMarkup()
    component.add(MenuKeyboardButton(Command.CANCEL))
    await message.chat.send("لطفا نام کد تخفیف را وارد کنید: ", components=component)

    answer_object = await wait_callback(client, callback)
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

    component = InlineKeyboardMarkup()
    component.add(InlineKeyboardButton("انصراف", callback_data=InlineCommands.RETURN))
    ask_object = await callback.message.reply("لطفا کد تحفیف را وارد کتید:", components=component)

    answer_object = await wait_callback(client, callback)
    await ask_object.delete()

    await transaction.update(code=answer_object.content)
    await transaction.update(status=Status.DELIVERED)

    component = InlineKeyboardMarkup()
    component.add(InlineKeyboardButton("کد ارسال شده!"))
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

    component = MenuKeyboardMarkup()
    component.add(MenuKeyboardButton("بله"))
    component.add(MenuKeyboardButton("خیر"))
    ask_object = await callback.message.reply("ایا از حذف تراکنش اطمینان دارید؟", components=component)

    answer_object = await wait_callback(client, callback)
    await ask_object.delete()

    if answer_object.content == "بله":
        await transaction.update(status=Status.CANCELED)
        await customer.update(balance=(customer.balance + transaction.price))
        text = f"""
        تراکنش با ایدی {transaction.id} از طرف مدیریت لفو شد!
         مبلغ {transaction.price}  به حساب کاربری شما بازگشت خورد!
        """
        await client.send_message(customer.user_id, text)

        component = InlineKeyboardMarkup()
        component.add(InlineKeyboardButton("تراکنش لغو شده!"))
        await callback.message.edit(callback.message.content, components=component)

        await answer_object.reply("تراکنش با موفقیت لغو شد!")
        return await panel_handler(client, callback.message, user)

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
    if not message:
        return

    if message.content.startswith("/start") or message.content == "/panel":
        return

    try:
        return await commands[message.content](client, message, user)
    except KeyError:
        if step == InlineCommands.SEND_DISCOUNT:
            return
        await client.send_message(user.user_id, "دستور یافت نشد!")
        answer_object = await wait_message(client, message)
        return await answer_checker(client, answer_object, user)
    except Exception as e:
        print(e)
        return


async def callback_checker(client: Bot, callback: CallbackQuery, user: User):
    # to cut the extra arguments
    command = ":".join(callback.data.split(':')[:2])
    return await commands[command](client, callback, user)
