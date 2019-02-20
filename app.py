from flask import Flask, render_template, request, url_for, redirect, flash, abort, jsonify
from flask_login import LoginManager, login_required, login_user, current_user, logout_user
import jinja2
from models import User, Post, PostUser, Tag, PostTag, Settings, postgres_db
from functools import wraps
import json
import bcrypt
import markdown
import datetime
import peewee
from mdx_gfm import GithubFlavoredMarkdownExtension as GithubMarkdown
from playhouse.shortcuts import model_to_dict
from playhouse.postgres_ext import *
from pagination import Pagination
import util

app = Flask(__name__)
app.config.from_object("config.Config")

auth = LoginManager()
auth.init_app(app)
auth.login_view = "login"
auth.login_message = "You must be logged in to access that page."
auth.login_message_category = "danger"


# TODO: Refactor: everything
# TODO: Refactor: CSS Class names ( _ -> - ), and CSS IDs
# TODO: Refactor: Structure of CSS
# TODO: Refactor: Structure of app.py
# TODO: Refactor: SQL Queries
# TODO: Minimize static components
# TODO: Slugs


@app.context_processor
def recent_post_context_processor():
    settings = util.get_current_settings()
    return {'recent_posts': Post.select().order_by(Post.created_at.desc()).limit(settings.number_of_recent_posts)}

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
    values = {'settings': settings}
    return values


@app.template_filter('Markdown')
def filter_markdown(raw_markdown):
    return jinja2.Markup(markdown.markdown(raw_markdown, extensions=[GithubMarkdown()]))


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

    # Adding gin index to Post.content and Tag.name for faster search
    language = 'english'

    Post.add_index(
        SQL("CREATE INDEX post_full_text_search ON post USING GIN(to_tsvector('" + language + '\',content))'))
    Tag.add_index(
        SQL("CREATE INDEX tag_full_text_search ON tag USING GIN(to_tsvector('" + language + '\', name))'))


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
        flash("Created user: admin", 'success')

    except peewee.IntegrityError:
        flash("User admin already exists", 'danger')

    if current_user.is_authenticated:
        return redirect(url_for('admin_user_list'))
    else:
        return redirect(url_for('login'))


@app.route('/index')
@app.route('/')
def index():
    return redirect("blog")


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


@app.route('/blog/archive/<int:page>')
@app.route('/blog/archive', defaults={'page': 1})
@app.route('/blog', defaults={'page': 1})
def blog(page):
    settings = util.get_current_settings()

    posts_with_tags = []
    if current_user.is_authenticated:
        if current_user.admin:
            posts = Post.select().order_by(Post.created_at.desc())
    else:
        posts = Post.select().where(Post.published).order_by(Post.created_at.desc())

    total_posts = Post.select().count()
    posts = posts.paginate(page, settings.posts_per_page)

    for post in posts:
        tags = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        posts_with_tags.append([post, tags])

    pages = Pagination(page, settings.posts_per_page, total_posts, 7)

    return render_template('blog.html', posts_with_tags=posts_with_tags, pages=pages)


@app.route('/post/<int:pid>')
def post(pid, ):
    post = None
    try:
        post = Post.get(Post.id == pid)
        tags = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        user = User.select().join(PostUser, peewee.JOIN.LEFT_OUTER).where(PostUser.post == post)
        if user:
            user = user[0]
    except Post.DoesNotExist:
        abort(404)
    return render_template('post_view.html', post=post, tags=tags, user=user)


@app.route('/tag/<tag_name>', defaults={'page': 1})
@app.route('/tag/<tag_name>/<int:page>')
def tag_view(tag_name, page):
    settings = util.get_current_settings()

    if current_user.is_authenticated:
        if current_user.admin:
            matches = Post.select().join(PostTag).join(Tag).where(Tag.name == tag_name).order_by(
                Post.created_at.desc())
    else:
        matches = Post.select().where(Post.published).join(PostTag).join(Tag).where(Tag.name == tag_name).order_by(
            Post.created_at.desc())

    total_matches = matches.count()
    matches = matches.paginate(page, settings.posts_per_page)

    matches_with_tags = []
    for match in matches:
        tags = Tag.select().join(PostTag).where(PostTag.post == match).order_by(Tag.name)
        matches_with_tags.append([match, tags])

    pages = Pagination(page, settings.posts_per_page, total_matches, 7)
    # .order_by(Post.created_at.desc()).limit(5)

    if not len(matches) == 0:
        return render_template('tag_view.html', posts_with_tags=matches_with_tags, pages=pages, tag_name=tag_name)
    else:
        return render_template('404.html', notice="No posts with this tag")


@app.route('/user/<user_name>', defaults={'page': 1})
@app.route('/user/<user_name>/<int:page>')
def user_view(user_name, page):
    settings = util.get_current_settings()

    if current_user.is_authenticated:
        if current_user.admin:
            matches = Post.select().join(PostUser).join(User).where(User.name == user_name).order_by(
                Post.created_at.desc())
    else:
        matches = Post.select().where(Post.published).join(PostUser).join(User).where(User.name == user_name).order_by(
            Post.created_at.desc())

    total_matches = matches.count()
    matches = matches.paginate(page, settings.posts_per_page)

    matches_with_tags = []
    for match in matches:
        tags = Tag.select().join(PostTag).where(PostTag.post == match).order_by(Tag.name)
        matches_with_tags.append([match, tags])

    pages = Pagination(page, settings.posts_per_page, total_matches, 7)
    # .order_by(Post.created_at.desc()).limit(5)
    if not len(matches) == 0:
        return render_template('user_view.html', posts_with_tags=matches_with_tags, pages=pages, user_name=user_name)
    return render_template('404.html', notice="No posts by this user")


@app.route('/search', methods=["POST"])
def search():
    query = request.form.get('navbar-search-input')
    return redirect(url_for('search_view', query=query))


@app.route('/search/<query>', defaults={'page': 1})
@app.route('/search/<query>/<int:page>')
def search_view(query, page):
    settings = util.get_current_settings()
    query = "\'" + query + "\'" # the quotation marks are absolutely necessary for a pg tsquery with multiple words

    if current_user.is_authenticated:
        if current_user.admin:
            posts_matched_content = Post.select()\
                .where((Match(Post.content, query) == True))
            posts_matched_title = Post.select()\
                .where((Match(Post.title, query) == True) & (Match(Post.content, query) == False))
            posts_matched_tag = Post.select().join(PostTag).join(Tag)\
                .where((Match(Tag.name, query) == True) & (Match(Post.title, query) == False) & (Match(Post.content, query) == False))



    else:
        posts_matched_content = Post.select()\
                .where((Post.published == True) & (Match(Post.content, query) == True))
        posts_matched_title = Post.select()\
                .where((Post.published == True) & (Match(Post.title, query) == True) & (Match(Post.content, query) == False))
        posts_matched_tag = Post.select().join(PostTag).join(Tag) \
                .where((Post.published == True) & (Match(Tag.name, query) == True) & (Match(Post.title, query) == False) & (Match(Post.content, query) == False))

    posts_matched = posts_matched_content + posts_matched_title + posts_matched_tag

    total_posts = posts_matched.count()
    posts_matched = posts_matched.paginate(page, settings.posts_per_page)

    posts_with_tags = []


    for post in posts_matched:
        tags = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        posts_with_tags.append([post, tags])

    pages = Pagination(page, settings.posts_per_page, total_posts, 7)
    return render_template('search_view.html', posts_with_tags=posts_with_tags, pages=pages, query=query, current=search_view)


@app.route('/admin/preview', methods=["POST"])
@login_required
@admin_required
def preview():
    html = markdown.markdown(request.form['post_content_as_markdown'], extensions=[GithubMarkdown()])
    date_time = datetime.datetime.now().strftime("%B %d, %Y")
    return jsonify(html=html, date_time=date_time)


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
        post = Post.get(pid == Post.id)
        tags_of_post = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        all_tags = Tag.select()
    except Post.DoesNotExist:
        abort(404)

    return render_template('compose.html', editing=True, pid=pid, post=post, tags_of_post=tags_of_post,
                           all_tags=all_tags)


@app.route('/admin/posts/save', methods=["POST"])
@login_required
@admin_required
def admin_save_post():
    edit_id = request.form.get('post-edit-id')
    title = request.form.get('post-title')
    slug = util.slugify(title)
    content = request.form.get('post-content')
    description = request.form.get('post-description')
    tags_json = json.loads(request.form.get('post-tags'))
    tags = [ tag_json["value"] for tag_json in tags_json ]
    publish = True if request.form.get('post-publish') == 'on' else False

    if edit_id:
        try:
            post = Post.get(Post.id == edit_id)
            post.title = title
            post.content = content
            post.slug = slug
            post.description = description
            post.updated_at = datetime.datetime.now()
            post.published = publish
            post.save()

            for tag in tags:
                tag, _ = Tag.get_or_create(name=tag)
                PostTag.get_or_create(post=post, tag=tag)

            old_tags = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
            for old_tag in old_tags:
                if not old_tag in tags:
                    PostTag.get(PostTag.post == post, PostTag.tag == old_tag).delete_instance()

            flash("Post edited!", "success")

        except Post.DoesNotExist:
            abort(404)

    else:
        try:
            post = Post(title=title,
                        content=content,
                        slug=slug,
                        description=description,
                        published=publish)
            post.save()
            postuser = PostUser(post=post, user=current_user.id)
            postuser.save()

            for tag_name in tags:
                tag, _ = Tag.get_or_create(name=tag_name)
                PostTag.get_or_create(post=post, tag=tag)


            if publish:
                flash("Post published!", "success")
            elif not publish:
                flash("Post saved as draft!", "success")

        except peewee.IntegrityError:
            abort(404)

    return redirect(url_for('admin_post_list'))


@app.route('/admin')
@login_required
@admin_required
def admin_main():
    return redirect(url_for('admin_post_list'))


@app.route('/admin/posts')
@login_required
@admin_required
def admin_post_list():
    posts = Post.select()

    posts_with_user_and_tags = []
    for post in posts:
        tags = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        user = User.select().join(PostUser, peewee.JOIN.LEFT_OUTER).where(PostUser.post == post)
        if user:
            user = user[0]  # Accessing the first (and only) result of the query... if a postuser existed
        posts_with_user_and_tags.append([post, user, tags])


    order_by = request.args.get('order_by')
    order = request.args.get('order')

    if (order_by == 'title' and order == 'asc' ):
        posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[0].title.lower() )
    elif(order_by == 'title' and order == 'desc' ):
        posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[0].title.lower(), reverse=True )
    elif (order_by == 'user' and order == 'asc'):
        posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[1].name.lower() )
    elif (order_by == 'user' and order == 'desc'):
        posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[1].name.lower(), reverse=True )
    elif (order_by == 'updated_at' and order == 'asc'):
        posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[0].updated_at )
    else:
        posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[0].updated_at, reverse=True )
        order_by = 'updated_at'
        order = 'desc'
    return render_template('post_list.html', posts_with_user_and_tags=posts_with_user_and_tags, order_by=order_by, order=order)


@app.route('/admin/posts/delete', methods=["POST"])
@login_required
@admin_required
def admin_post_delete():
    status = {'ok': True}

    if 'id' not in request.form:
        abort(400)

    id_to_delete = request.form.get('id', None)

    if id_to_delete:
        try:
            post_to_delete = Post.get(Post.id == id_to_delete)
            posttags_to_delete = PostTag.select().where(PostTag.post == post_to_delete)
            for posttag_to_delete in posttags_to_delete:
                posttag_to_delete.delete_instance()
            postuser_to_delete = PostUser.select().where(PostUser.post == post_to_delete)[0]
            postuser_to_delete.delete_instance()
            post_to_delete.delete_instance()

            if request.form.get('was_edit', None) and request.form.get('was_edit', None) == 'true':
                flash('Deleted post ' + str(post_to_delete.id) + ' !', "success")

        except Post.DoesNotExist:
            flash("Post does not exist, please look into the sql table", "danger")
            status['ok'] = False

            #       except peewee.IntegrityError:
            #           flash("Peewee.IntegrityError there seems to be a foreign key constraint error", "danger")
            #           status['ok'] = False
    else:
        status['ok'] = False

    # return json.dumps({ "message" : "Deleted post.", "status" : "success"})
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
    all_tags = Tag.select()
    return render_template('tag_edit.html', editing=False, tags=False, all_tags = Tag.select()
)


@app.route('/admin/tags/edit/<uid>')
@login_required
@admin_required
def admin_tag_edit(uid):
    try:
        tag_to_edit = Tag.get(Tag.id == uid)
    except Tag.DoesNotExist:
        abort(404)
    return render_template('tag_edit.html', editing=True, tag_to_edit=tag_to_edit, all_tags = Tag.select().where(Tag.id != tag_to_edit.id  ) )


@app.route('/admin/tags/save', methods=["POST"])
@login_required
@admin_required
def admin_tag_save():

    tags_json = json.loads(request.form.get('tags'))
    tags = [ tag_json["value"] for tag_json in tags_json ]
    edit_id = request.form.get('tag-edit-id')

    if edit_id:
        try:
            tag_to_edit = Tag.get(Tag.id == edit_id)
            tag_to_edit.name = tags[0]
            tag_to_edit.save()
            flash("Tag edited", "success")

        except Tag.DoesNotExist:
            abort(404)

    else:
        successes = []
        for tag in tags:
            t, created = Tag.get_or_create(name=tag)
            successes.append(created)



        if successes.count(True) == 1:
            flash("Tag \"" + ", ".join( [tag for tag,success in zip(tags, successes) if success == True ] ) + "\" created!", "success")
        elif successes.count(True) > 1:
            flash("Tags \"" + ", ".join( [tag for tag,success in zip(tags, successes) if success == True ] ) + "\" created!", "success")

        if successes.count(False) == 1:
            flash("Tag \"" + ", ".join( [tag for tag, success in zip(tags, successes) if success == False ]) + "\" already existed!", "danger")
        elif successes.count(False) > 1:
            flash("Tags \"" + ", ".join( [tag for tag,success in zip(tags, successes) if success == False ]) + "\" already existed!", "danger")

    return redirect(url_for('admin_tag_list'))


@app.route('/admin/tags/delete', methods=["POST"])
@login_required
@admin_required
def admin_tag_delete():
    status = {'ok': True}

    if 'id' not in request.form:
        abort(400)

    id_to_delete = request.form.get('id', None)

    if id_to_delete:
        try:
            tag_to_delete = Tag.get(Tag.id == id_to_delete)
            posttags_to_delete = PostTag.select().where(PostTag.tag == tag_to_delete)
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
    return render_template('user_edit.html', editing=False, )


def user_edit(uid):
    try:
        user_to_edit = User.get(User.id == uid)
    except User.DoesNotExist:
        abort(404)

    if user_to_edit.id == current_user.id:
        return render_template('user_edit.html', editing=True, user=user_to_edit, selfediting=True)
    else:
        return render_template('user_edit.html', editing=True, user=user_to_edit, selfediting=False)


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
        User.create(name=username, password=hashed_pw, admin=is_admin)
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

    id_to_save = int(request.form.get('user-edit-id', None))  # request returns strings, not ints!

    if id_to_save == current_user.id:
        return user_save()
    elif id_to_save != current_user.id:
        abort(400)


def user_delete():
    status = {'ok': True}

    if 'id' not in request.form:
        abort(400)

    id_to_delete = request.form.get('id', None)  # request returns strings, not ints!

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

    id_to_delete = int(request.form.get('id', None))  # request returns strings, not ints!

    if id_to_delete == current_user.id:
        status = {'ok': False}
        flash(
            "You can't delete yourself via this table. If you are sure you wan't to delete yourself, please use the \
             delete option in your profile,",
            "danger")
        return json.dumps(status)

    elif id_to_delete != current_user.id:
        return user_delete()


@app.route('/profile/delete', methods=["POST"])
@login_required
def profile_user_delete():
    if 'id' not in request.form:
        abort(400)

    id_to_delete = int(request.form.get('id', None))  # request returns strings, not ints!

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


@app.errorhandler(404)
def page_not_found(e):
    notice = """Nothing to see here"""
    return render_template('404.html', notice=notice), 404



if __name__ == '__main__':
    app.debug = True
    app.run()

