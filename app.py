from flask import Flask, render_template, request, url_for, redirect, flash, abort
from flask_login import LoginManager, login_required, login_user, current_user, logout_user
from jinja2 import Markup
from models import User, Post, PostUser, Tag, PostTag, Settings, postgres_db
from functools import wraps
import json
import bcrypt
import markdown
import datetime
import peewee
from peewee import fn
from mdx_gfm import GithubFlavoredMarkdownExtension as GithubMarkdown
from playhouse.shortcuts import model_to_dict
from playhouse.postgres_ext import *

ext_db = PostgresqlExtDatabase('peewee_test', user='postgres')

class BaseExtModel(Model):
    class Meta:
        database = ext_db
from pagination import Pagination
import util

app = Flask(__name__)
app.config.from_object("config.Config")

auth = LoginManager()
auth.init_app(app)
auth.login_view = "login"
auth.login_message = "You must be logged in to access that page."
auth.login_message_category = "danger"

@app.context_processor
def recent_post_context_processor():
    settings = util.get_current_settings()
    return { 'recent_posts':
            Post.select().order_by(Post.created_at.desc()).limit(settings.number_of_recent_posts)}

# @app.context_processor
# def top_tags_context_processor():
#     values = {}
#
#     all_tags = {}
#     for post in Post.select():
#         for tag in post.tags.split(';'):
#             if tag in all_tags:
#                 all_tags[tag] += 1
#             else:
#                 all_tags[tag] = 1
#
#     sorted_tags = ((k, all_tags[k]) for k in sorted(all_tags, key=all_tags.get, reverse=True))
#
#     values['top_tags'] = list(sorted_tags)[0:10]
#     return values

@app.context_processor
def settings_context_processor():
    settings = model_to_dict(util.get_current_settings())

    values = {}
    values['settings'] = settings
    return values

@app.template_filter('Markdown')
def filter_markdown(raw_markdown):
    return Markup(markdown.markdown(raw_markdown, extensions=[GithubMarkdown()]))

def admin_required(f):
    @wraps(f)

    def wrapper(*args, **kwargs):
        if not current_user.admin:
            flash("You need administrator privileges to access this page.", "danger")
            return redirect(url_for('blog'))
        return f(*args, **kwargs)

    return wrapper

@auth.user_loader
def user_loader(uid):
    user = None
    try:
        user = User.get(User.id == uid)
    except User.DoesNotExist:
        pass

    return user

@app.before_first_request
def setup_database():
    postgres_db.create_tables([User, Post, PostUser, Tag, PostTag, Settings], safe=True)

# @app.before_request
# def before_request():
#     postgres_db.connect()
#
# @app.after_request
# def after_request(response):
#     postgres_db.close()
#     return response

@app.route('/init')
def init_user():
    try:
        User.create(name="admin", password=bcrypt.hashpw(b"password", bcrypt.gensalt()), admin=True)
        flash("Created user: Admin", 'success')

    except peewee.IntegrityError:
        flash("User Admin already exists", 'danger')

    if current_user.is_authenticated:
        return redirect(url_for('admin_user_list'))
    else:
        return redirect(url_for('login'))


@app.route('/')
def index():
    return redirect(url_for('blog'))

@app.route('/login')
def login():
    if current_user.is_authenticated:
        if current_user.admin:
            return redirect(url_for('admin_main'))
        elif not current_user.admin:
            return redirect(url_for('blog'))
    else:
        return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/login/go', methods=["POST"])
def do_login():

    username = request.form.get("username", False)
    password = request.form.get("password", False)

    if username and password:
        try:
            u = User.get(User.name == username)
            if bcrypt.hashpw(password.encode(), u.password.encode()) == u.password.encode():
                login_user(u)
                requested_page = request.args.get('next')
                default_page = url_for('admin_main') if u.admin else url_for('blog')
                return redirect(requested_page or default_page)
            else:
                flash("Username or password incorrect.", "danger")
                return redirect(url_for('login'))
        except User.DoesNotExist:
            flash("User does not exist.", "danger")
    else:
        flash("Username and password required.", "danger")

    return redirect(url_for('login'))

@app.route('/blog', defaults={'page' : 1})
@app.route('/blog/archive/<int:page>')
def blog(page):
    settings = util.get_current_settings()

    posts_with_tags = []
    posts = Post.select().order_by(Post.created_at.desc()).paginate(page,settings.posts_per_page)
    for post in posts:
        tags = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        posts_with_tags.append([post, tags])


    total_posts = Post.select().count()
    pages = Pagination(page, settings.posts_per_page, total_posts, 7)

    return render_template('blog_list.html', posts_with_tags=posts_with_tags, pages=pages)

@app.route('/post/<int:pid>')
@app.route('/post/<int:pid>/<slug>')
def post(pid, slug=None):
    post = None
    try:
        post = Post.get(Post.id == pid)
    except Post.DoesNotExist:
        abort(404)
    return render_template('post_view.html', post=post)

@app.route('/tag/<tag>', defaults={'page' : 1})
@app.route('/tag/<path:tag>/<int:page>')
def view_tag(tag, page):
    settings = util.get_current_settings()

    matches = Post.select().join(PostTag).join(Tag).where(Tag.name == (tag)).order_by(Post.created_at.desc()).paginate(page, settings.posts_per_page)

    matches_with_tags = []
    for match in matches:
        tags = Tag.select().join(PostTag).where(PostTag.post == match).order_by(Tag.name)
        matches_with_tags.append([match, tags])

    total_matches = matches.count()
    pages = Pagination(page, settings.posts_per_page, total_matches, 7)
#.order_by(Post.created_at.desc()).limit(5)
    return render_template('blog_list.html', posts_with_tags=matches_with_tags, pages=pages)

@app.route('/user/<user>', defaults={'page' : 1})
@app.route('/user/<path:user>/<int:page>')
def view_user(user, page):
    settings = util.get_current_settings()

    matches = Post.select().join(PostUser).join(User).where(User.name == (user)).order_by(Post.created_at.desc()).paginate(page, settings.posts_per_page)

    matches_with_tags = []
    for match in matches:
        tags = Tag.select().join(PostTag).where(PostTag.post == match).order_by(Tag.name)
        matches_with_tags.append([match, tags])

    total_matches = matches.count()
    pages = Pagination(page, settings.posts_per_page, total_matches, 7)
#.order_by(Post.created_at.desc()).limit(5)
    return render_template('blog_list.html', posts_with_tags=matches_with_tags, pages=pages)


@app.route('/admin/preview', methods=["POST"])
@login_required
@admin_required
def preview():
    html = markdown.markdown(request.form['post-content'], extensions=[GithubMarkdown()])
    return html

@app.route('/admin/posts/compose')
@login_required
@admin_required
def compose():
    all_tags = Tag.select()
    return render_template('compose.html', editing=False, all_tags=all_tags)

@app.route('/admin/posts/edit/<pid>')
@login_required
@admin_required
def admin_edit_post(pid):
    post = None

    try:
        post = Post.get(Post.id == pid)
        tags_of_post = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        all_tags = Tag.select()
    except Post.DoesNotExist:
        abort(404)

    return render_template('compose.html', editing=True, pid=pid, post=post, tags_of_post=tags_of_post, all_tags=all_tags)

@app.route('/admin/posts/save', methods=["POST"])
@login_required
@admin_required
def admin_save_post():

    edit_id = request.form.get('post-edit-id')
    title = request.form.get('post-title')
    slug = util.slugify(title)
    content = request.form.get('post-content')
    description = request.form.get('post-description')
    tags = list(filter(None, request.form.get('post-tags').split(',')))

    if edit_id:
        try:
            post = Post.get(Post.id == edit_id)
            post.title = title
            post.content = content
            post.slug = slug
            post.description = description
            post.updated_at = datetime.datetime.now()
            post.save()

            for tag_name in tags:
                tag, __ = Tag.get_or_create(name=tag_name)
                posttag, __ = PostTag.get_or_create(post=post, tag=tag)

            flash("Post edited!", "success")

        except Post.DoesNotExist:
            abort(404)

    else:
        try:
            post = Post(title=title,
                        content=content,
                        slug=slug,
                        description=description)
            post.save()
            postuser = PostUser(post=post, user = current_user.id)
            postuser.save()

            for tag_name in tags:
                tag, __ = Tag.get_or_create(name=tag_name)
                posttag, __ = PostTag.get_or_create(post=post, tag=tag)

            flash("Post created!", "success")

        except peewee.IntegrityError:
            abort(404)

    return redirect(url_for('admin_post_list'))

@app.route('/admin')
@login_required
@admin_required
def admin_main():
    return render_template('post_list.html', posts=Post.select())


@app.route('/admin/posts')
@login_required
@admin_required
def admin_post_list():
    posts = Post.select().order_by(Post.created_at.desc())
    posts_with_user_and_tags=[]
    for post in posts:
        tags = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        user = User.select().join(PostUser, peewee.JOIN.LEFT_OUTER).where(PostUser.post == post)
        if user:
            user=user[0] # Accessing the first (and only) result of the query... if a postuser existed
        posts_with_user_and_tags.append([post, user, tags])
    return render_template('post_list.html', posts_with_user_and_tags=posts_with_user_and_tags)

@app.route('/admin/posts/delete', methods=["POST"])
@login_required
@admin_required
def admin_post_delete():
    status = {}
    status['ok'] = True

    if 'id' not in request.form:
        abort(400)

    id_to_delete = request.form.get('id', None)

    if id_to_delete:
        try:
            post_to_delete = Post.get(Post.id==id_to_delete)
            posttags_to_delete = PostTag.select().where(PostTag.post == post_to_delete)
            for posttag in posttags_to_delete:
                posttag.delete_instance()
            post_to_delete.delete_instance()

        except Post.DoesNotExist:
            flash("Post does not exist, please look into the sql table", "danger")
            status['ok'] = False

        except peewee.IntegrityError:
            flash("Peewee.IntegrityError there seems to be a foreign key constraint error", "danger")
            status['ok'] = False
    else:
        status['ok'] = False


    #return json.dumps({ "message" : "Deleted post.", "status" : "success"})
    return json.dumps(status)


@app.route('/admin/tags')
@login_required
@admin_required
def admin_tag_list():
    tags_with_post_counts = Tag.select(Tag, fn.Count(Post.id).alias('count')) \
        .join(PostTag, peewee.JOIN.LEFT_OUTER) \
        .join(Post, peewee.JOIN.LEFT_OUTER) \
        .group_by(Tag) \
        .limit(20)
    return render_template('tag_list.html', tags=tags_with_post_counts)


@app.route('/admin/tags/create')
@login_required
@admin_required
def admin_tag_create():
    return render_template('edit_tag.html', tags=False)

@app.route('/admin/tags/edit/<uid>')
@login_required
@admin_required
def admin_tag_edit(uid):
    try:
        tag_to_edit = Tag.get(Tag.id == uid)
    except Tag.DoesNotExist:
        abort(404)
    return render_template('edit_tag.html', editing=True, tag=tag_to_edit)

@app.route('/admin/tags/save', methods=["POST"])
@login_required
@admin_required
def admin_tag_save():

    tagname = request.form.get('tag-name')
    edit_id = request.form.get('tag-edit-id')

    if edit_id:
        try:
            tag_to_edit = Tag.get(Tag.id == edit_id)
            tag_to_edit.name = tagname
            tag_to_edit.save()
            flash("Tag edited", "success")

        except Tag.DoesNotExist:
            abort(404)

    else:
        t, created = Tag.get_or_create(name=tagname)
        if created:
            flash("Tag created!", "success")
        else:
            flash("Tag already existed!", "danger")

    return redirect(url_for('admin_tag_list'))

@app.route('/admin/tags/delete', methods=["POST"])
@login_required
@admin_required
def admin_tag_delete():
    status = {}
    status['ok'] = True

    if 'id' not in request.form:
        abort(400)

    id_to_delete = request.form.get('id', None)

    if id_to_delete:
        try:
            tag_to_delete = Tag.get(Tag.id == id_to_delete)
            posttags_to_delete = PostTag.select().where(PostTag.tag == tag_to_delete )
            for posttag in posttags_to_delete:
                posttag.delete_instance()
            tag_to_delete.delete_instance()

        except Tag.DoesNotExist:
            status['ok'] = False

    return json.dumps(status)



@app.route('/admin/users')
@login_required
@admin_required
def admin_user_list():
    users_with_post_counts = User.select(User, fn.Count(Post.id).alias('count')) \
        .join(PostUser, peewee.JOIN.LEFT_OUTER) \
        .join(Post, peewee.JOIN.LEFT_OUTER) \
        .group_by(User) \
        .limit(20)  # JOIN.LEFT_OUTER, so that users get included that posses no posts
                    # fn.Count().alias('count') adds count as an attribute to users
    return render_template('user_list.html', users_with_post_counts=users_with_post_counts)


@app.route('/admin/users/create')
@login_required
@admin_required
def admin_user_create():
    return render_template('edit_user.html', editing=False, )


def user_edit(uid):
    try:
        user_to_edit = User.get(User.id == uid)
    except User.DoesNotExist:
        abort(404)

    if user_to_edit.id == current_user.id:
        return render_template('edit_user.html', editing=True, user=user_to_edit, selfediting=True)
    else:
        return render_template('edit_user.html', editing=True, user=user_to_edit, selfediting=False)

@app.route('/admin/users/edit/<uid>')
@login_required
@admin_required
def admin_user_edit(uid):
    return user_edit(uid)


@app.route('/profile')
@login_required
def profile_user_edit():
    current_user_id = current_user.id
    return user_edit(current_user_id)


def user_save():
    username = request.form.get('user-name')
    password = request.form.get('user-password')
    is_admin = request.form.get('user-is-admin') == 'on'
    edit_id = request.form.get('user-edit-id')

    if edit_id:
        try:
            user_to_edit = User.get(User.id == edit_id)

            hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            user_to_edit.name = username
            user_to_edit.password = hashed_pw
            user_to_edit.admin = is_admin

            user_to_edit.save()
            flash("User edited", "success")
        except User.DoesNotExist:
            abort(404)

    else:

        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        u = User.create(name=username, password=hashed_pw, admin=is_admin)
        flash("User created!", "success")

    if is_admin:
        return redirect(url_for('admin_user_list'))
    else:
        return redirect(url_for('blog'))


@app.route('/admin/users/save', methods=["POST"])
@login_required
@admin_required
def admin_user_save():
    return user_save()

@app.route('/profile/save', methods=["POST"])
@login_required
def profile_user_save():

    if 'user-edit-id' not in request.form:
        abort(400)

    id_to_save = int(request.form.get('user-edit-id', None)) # request returns strings, not ints!

    if id_to_save == current_user.id:
        return user_save()
    elif id_to_save != current_user.id:
        abort(400)

def user_delete():
    status = {}
    status['ok'] = True

    if 'id' not in request.form:
        abort(400)

    id_to_delete = request.form.get('id', None) # request returns strings, not ints!

    if id_to_delete:
        try:
            user_to_delete = User.get(User.id == id_to_delete)
            postusers_to_delete = PostUser.select().where(PostUser.user == user_to_delete)
            for postuser in postusers_to_delete:
                postuser.delete_instance()
            user_to_delete.delete_instance()

        except User.DoesNotExist:
            flash("User does not exist, please look into the sql table", "danger")
            status['ok'] = False

        except peewee.IntegrityError:
            flash("peewee.IntegrityError there seems to be a foreign key constraint error", "danger")
            status['ok'] = False

    return json.dumps(status)

@app.route('/admin/users/delete', methods=["POST"])
@login_required
@admin_required
def admin_user_delete():
    if 'id' not in request.form:
        abort(400)

    id_to_delete = int(request.form.get('id', None)) # request returns strings, not ints!

    if id_to_delete == current_user.id:
        status = {}
        status['ok'] = False
        flash("You can't delete yourself via this table. If you are sure you wan't to delete yourself, please use the delete option in your profile,", "danger")
        return json.dumps(status)

    elif id_to_delete != current_user.id:
        user_delete()

@app.route('/profile/delete', methods=["POST"])
@login_required
def profile_user_delete():

    if 'id' not in request.form:
        abort(400)

    id_to_delete = int(request.form.get('id', None)) # request returns strings, not ints!

    if id_to_delete == current_user.id:
        return user_delete()
    elif id_to_delete != current_user.id:
        abort(400)


@app.route('/admin/settings')
@login_required
@admin_required
def admin_settings():
    current_settings = util.get_current_settings()

    return render_template("admin_settings.html", current_settings=current_settings)

@app.route('/admin/settings/save', methods=["POST"])
@login_required
@admin_required
def admin_settings_save():
    current_settings = None
    try:
        current_settings = Settings.get(Settings.id == 1)
        current_settings.blog_title = request.form.get('blog-title')
        current_settings.icon_1_link = request.form.get('icon-1-link')
        current_settings.icon_1_icon_type = request.form.get('icon-1-icon-type')
        current_settings.icon_2_link = request.form.get('icon-2-link')
        current_settings.icon_2_icon_type = request.form.get('icon-2-icon-type')
        current_settings.posts_per_page = request.form.get('posts-per-page')
        current_settings.number_of_recent_posts = request.form.get('number-of-recent-posts')
        current_settings.max_synopsis_chars = request.form.get('max-synopsis-chars')
        current_settings.save()

        flash("Settings updated.", "success")
    except Settings.DoesNotExist:
        flash("Please try again.", "danger")

    return redirect(url_for('admin_settings'))
if __name__ == '__main__':
    app.debug = True
    app.run()

