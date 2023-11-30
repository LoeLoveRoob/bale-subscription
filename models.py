import asyncio
import databases
import orm

from enum import Enum

database = databases.Database("sqlite+aiosqlite:///database.sqlite")
models = orm.ModelRegistry(database)


class Role(Enum):
    ADMIN = 1
    USER = 2

class Status(Enum):
    PENDING = 0
    CANCELED = 1
    DELIVERED = 2



class User(orm.Model):
    id: int
    from_id: int
    user_id: int
    role: str
    balance: int
    name: str
    father_name: str
    national_code: int

    tablename = "users"
    registry = models
    fields = dict(
        id=orm.Integer(primary_key=True),
        from_id=orm.Integer(allow_null=True, default=None),
        user_id=orm.Integer(unique=True),
        role=orm.Enum(Role),
        balance=orm.Integer(default=0),
        name=orm.String(max_length=255, allow_null=True, default=None),
        father_name=orm.String(max_length=255, allow_null=True, default=None),
        national_code=orm.String(allow_null=True, default=None, max_length=14),
    )


class Discount(orm.Model):
    id: int
    name: str

    tablename = "discount_type"
    registry = models
    fields = dict(
        id=orm.Integer(primary_key=True),
        name=orm.String(max_length=255),
    )


class DiscountUser(orm.Model):
    id: int
    discount: Discount
    user: User
    price: int
    code: str
    name: str
    father_name: str
    national_code: int

    tablename = "discount_user"
    registry = models
    fields = dict(
        id=orm.Integer(primary_key=True),
        discount=orm.ForeignKey(Discount),
        user=orm.ForeignKey(User),
        price=orm.Integer(),
        code=orm.String(max_length=255, allow_null=True, default=None),
        name=orm.String(max_length=255, allow_null=True, default=None),
        father_name=orm.String(max_length=255, allow_null=True, default=None),
        national_code=orm.String(allow_null=True, default=None, max_length=14),
        status=orm.Enum(Status),
    )

async def main():
    await models.create_all()


if __name__ == '__main__':
    asyncio.run(main())
