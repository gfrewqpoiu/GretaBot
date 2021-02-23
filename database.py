from peewee import Model, IntegerField, CharField, TextField
from playhouse.sqliteq import SqliteQueueDatabase

db = SqliteQueueDatabase("bot.db")


class BaseModel(Model):
    class Meta:
        database = db


class Quote(BaseModel):
    """Represents a Quote Message for Discord.

    Fields:
    guildId: int
    keyword: char
    result: text
    authorId: int"""

    guildId = IntegerField()
    keyword = CharField()
    result = TextField(null=False)
    authorId = IntegerField(null=False)


Quote.add_index(Quote.guildId, Quote.keyword)
