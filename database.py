from peewee import *
from playhouse.sqliteq import SqliteQueueDatabase

db = SqliteQueueDatabase("bot.db")


class BaseModel(Model):
    class Meta:
        database = db


class Quote(BaseModel):
    guildId = IntegerField()
    keyword = CharField()
    result = TextField(null=False)
    authorId = IntegerField(null=False)


Quote.add_index(Quote.guildId, Quote.keyword)
