import inspect
import datetime
import json

from peewee import SQL
from peewee_aio import AIOModel, Manager, fields


db = Manager("aiosqlite:////db/db.sqlite3")


@db.register
class Voicemail(AIOModel):
    created_at = fields.DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])


@db.register
class Configuration(AIOModel):
    name = fields.CharField(primary_key=True)
    value = fields.BlobField()
    _cache = {}

    @classmethod
    async def _get(cls, name, default):
        try:
            value = cls._cache[name]
        except KeyError:
            try:
                config = await cls.get(name=name)
            except cls.DoesNotExist:
                value = default
            else:
                value = json.loads(config.value)
            cls._cache[name] = value
        return value

    @classmethod
    async def _set(cls, name, value):
        await cls.replace(name=name, value=json.dumps(value, allow_nan=False, separators=(",", ":")))
        cls._cache[name] = value


class __config:
    TAKING_CALLS: bool = True

    def __getattribute__(self, name):
        try:
            attr = super().__getattribute__(name)
        except AttributeError:
            raise AttributeError(f"Invalid setting: {name}")
        return Configuration._get(name, attr)


config = __config()
config_set = Configuration._set


async def init_models():
    # Initialize tables
    for model in db.models:
        await model.create_table()
