from peewee import PostgresqlDatabase, Model, TextField, CharField, DateTimeField, ForeignKeyField, BooleanField, IntegerField, SQL
from playhouse.postgres_ext import PostgresqlExtDatabase # necessary for full text search
from datetime import datetime
from config import Config
import urllib.parse

db_parsed_url = urllib.parse.urlparse(Config.DATABASE_URL)
username = db_parsed_url.username
password = db_parsed_url.password
database = db_parsed_url.path[1:]
hostname = db_parsed_url.hostname
postgres_db = PostgresqlExtDatabase(
                database=database,
                user=username,
                password=password,
                host=hostname,
                autocommit=True,
                autorollback=True,
                register_hstore=True)

class User(Model):
    name = TextField(unique=True)
    admin = BooleanField(default=False)
    password = TextField()
    active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        return self.active

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    class Meta:
        database = postgres_db

class Post(Model):
    title = TextField()
    description = TextField()
    content = TextField()
    slug = TextField()
    published = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = postgres_db
# Adding gin index to Post.content before first request

class PostUser(Model):
    post = ForeignKeyField(Post, null=True)
    user = ForeignKeyField(User, null=True)

    class Meta:
        database = postgres_db
        indexes = (
            (('post', 'user'), True),  # Note the trailing comma!
        )

class Tag(Model):
    name = CharField(unique=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        database = postgres_db
# Adding gin index to Tag.name before first request


class PostTag(Model):
    post = ForeignKeyField(Post, null=True)
    tag = ForeignKeyField(Tag, null=True)

    class Meta:
        database = postgres_db
        indexes = (
            (('post', 'tag'), True),  # Note the trailing comma!
        )




class Settings(Model):

    blog_title = TextField()
    initialized = BooleanField()

    icon_1_link = TextField()
    icon_1_icon_type = TextField()
    icon_2_link =  TextField()
    icon_2_icon_type = TextField()

    posts_per_page = IntegerField()
    number_of_recent_posts = IntegerField()
    max_synopsis_chars = IntegerField()

    class Meta:
        database = postgres_db
