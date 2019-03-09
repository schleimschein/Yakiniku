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


# TODO: Proper Responsiveness
# TODO: Minimize static components

########################################
### Initializing and defining Stuff  ###
########################################

### Initialize app ###
app = Flask(__name__)
app.config.from_object("config.Config")


### Initialize database ###

# @app.before_request
# def before_request():
#     postgres_db.connect()
#
# @app.after_request
# def after_request(response):
#     postgres_db.close()
#     return response

# Before first request: Create database tables. Make sure to have the postgres extension 'hstore' installed on the db.
@app.before_first_request
def setup_database():
    # Create data tables
    postgres_db.create_tables([User, Post, PostUser, Tag, PostTag, Settings], safe=True)

    # Adding gin index to Post.content and Tag.name for faster search
    language = 'english'

    Post.add_index(
        SQL("CREATE INDEX post_full_text_search ON post USING GIN(to_tsvector('" + language + '\',content))'))
    Tag.add_index(
        SQL("CREATE INDEX tag_full_text_search ON tag USING GIN(to_tsvector('" + language + '\', name))'))


### Initialize authentification ###
auth = LoginManager()
auth.init_app(app)

# Define auth login behaviour
auth.login_view = "login"
auth.login_message = "You must be logged in to access that page."
auth.login_message_category = "danger"

# Wrapper that checks if current user is admin. If not return an error flash
def admin_required(f):
    @wraps(f) # Fixes docstrings and names of decorated function
    def wrapper(*args, **kwargs):
        if not current_user.admin:
            flash("You need administrator privileges to access this page.", "danger")
            return redirect(url_for('blog'))
        return f(*args, **kwargs)
    return wrapper

# Wrapper for getting a user by id
@auth.user_loader # Callback for retrieving a user object.
def user_loader(uid):
    user = None
    try:
        user = User.get(User.id == uid)
    except User.DoesNotExist:
        pass
    return user


### Jinja Templates ###

# Make settings available to all jinja templates
@app.context_processor
def settings_context_processor():
    settings = model_to_dict(util.get_current_settings())
    values = {'settings': settings}
    return values

# Create a jinja filter that can handle markdown
@app.template_filter('Markdown')
def filter_markdown(raw_markdown):
    return jinja2.Markup(markdown.markdown(raw_markdown, extensions=[GithubMarkdown()]))

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

# Uncomment this if you want the most used tags available to all jinja templates as a variable.
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

# Uncomment this if you want the most recents posts available on all sites as a jinja variable.
# @app.context_processor
# def recent_post_context_processor():
#     settings = util.get_current_settings()
#     return {'recent_posts': Post.select().order_by(Post.created_at.desc()).limit(settings.number_of_recent_posts)}




########################################
###             Routes               ###
########################################

# Create a standard admin user. Testing only!!!

if app.testing == True:
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

### Login / Logout ###

# Login view
@app.route('/login')
def login():
    if current_user.is_authenticated:
        if current_user.admin:
            return redirect(url_for('admin_main'))
        elif not current_user.admin:            # Being a user without being admin is a bit useless rightnow.
            return redirect(url_for('blog'))    # For extending?
    else:
        return render_template('login.html')

# Login
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
            flash("Username or password incorrect.", "danger")
    else:
        flash("Username and password required.", "danger")

    return redirect(url_for('login'))

# Logout
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


### Actual blog ###

# Index url redirects
@app.route('/index')
@app.route('/')
def index():
    return redirect("blog")

# Frontpage view
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

    number_of_posts = Post.select().count()
    posts = posts.paginate(page, settings.posts_per_page)

    for post in posts:
        tags = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        posts_with_tags.append([post, tags])

    pages = Pagination(page, settings.posts_per_page, number_of_posts, 7)

    if not number_of_posts == 0:
        return render_template('blog_list.html', posts_with_tags=posts_with_tags, pages=pages)
    else:
        notice = "No posts yet  :/"
        return render_template('notice.html', notice=notice)

# Post view
@app.route('/post/<int:pid>')
@app.route('/post/<int:pid>/<slug>')

def post(pid, slug=None):
    post = None
    try:
        post = Post.get(Post.id == pid)
        tags = Tag.select().join(PostTag).where(PostTag.post == post).order_by(Tag.name)
        user = User.select().join(PostUser, peewee.JOIN.LEFT_OUTER).where(PostUser.post == post)
        if user:
            user = user[0]
    except Post.DoesNotExist: # Since a non-existent post id leads to a query exception, the appropriate response is the
        abort(404)            # 404 error, not a notice
    return render_template('post_view.html', post=post, tags=tags, user=user)

# Blog view of all posts with a certain tag
@app.route('/tag/<tag_name>', defaults={'page': 1})
@app.route('/tag/<tag_name>/<int:page>')
def tag_view(tag_name, page):
    settings = util.get_current_settings()

    if current_user.is_authenticated:
        if current_user.admin:
            matches = Post.select().join(PostTag).join(Tag)\
                .where(Tag.name == tag_name).order_by(Post.created_at.desc())
    else:
        matches = Post.select().where(Post.published).join(PostTag).join(Tag)\
            .where(Tag.name == tag_name).order_by(Post.created_at.desc())

    number_of_matches = matches.count()
    matches = matches.paginate(page, settings.posts_per_page)

    matches_with_tags = []
    for match in matches:
        tags = Tag.select().join(PostTag)\
            .where(PostTag.post == match).order_by(Tag.name)
        matches_with_tags.append([match, tags])

    pages = Pagination(page, settings.posts_per_page, number_of_matches, 7)

    if not number_of_matches == 0:
        return render_template('tag_view.html', posts_with_tags=matches_with_tags, pages=pages, tag_name=tag_name)
    else:
        notice="No posts with tag " + '"' + str(tag_name) + '"!'
        return render_template('notice.html', notice=notice )

# Blog view of all posts by a certain user
@app.route('/user/<user_name>', defaults={'page': 1})
@app.route('/user/<user_name>/<int:page>')
def user_view(user_name, page):
    settings = util.get_current_settings()

    if current_user.is_authenticated:
        if current_user.admin:
            matches = Post.select().join(PostUser).join(User)\
                .where(User.name == user_name).order_by(Post.created_at.desc())
    else:
        matches = Post.select().where(Post.published).join(PostUser).join(User)\
            .where(User.name == user_name).order_by(Post.created_at.desc())

    number_of_matches = matches.count()
    matches = matches.paginate(page, settings.posts_per_page)

    matches_with_tags = []
    for match in matches:
        tags = Tag.select().join(PostTag)\
            .where(PostTag.post == match).order_by(Tag.name)
        matches_with_tags.append([match, tags])

    pages = Pagination(page, settings.posts_per_page, number_of_matches, 7)

    if not number_of_matches == 0:
        return render_template('user_view.html', posts_with_tags=matches_with_tags, pages=pages, user_name=user_name)
    else:
        notice = "No posts by user " + '"' + str(user_name) + '"!'
        return render_template('notice.html', notice=notice )


# Search
@app.route('/search', methods=["POST"])
def search():
    query = request.form.get('navbar-search-input')
    return redirect(url_for('search_view', query=query))

# Blog view of all search results (posts appear only once, despite several matches in title, content and tags)
@app.route('/search/<query>', defaults={'page': 1})
@app.route('/search/<query>/<int:page>')
def search_view(query, page):
    settings = util.get_current_settings()

    query_str = "\'" + query + "\'" # the quotation marks are absolutely necessary for a pg tsquery with multiple words

    if current_user.is_authenticated:
        if current_user.admin:
            posts_matched_content = Post.select()\
                .where((Match(Post.content, query_str) == True))
            posts_matched_title = Post.select()\
                .where((Match(Post.title, query_str) == True)
                       & (Match(Post.content, query_str) == False))
            posts_matched_tag = Post.select().join(PostTag).join(Tag)\
                .where((Match(Tag.name, query_str) == True)
                       & (Match(Post.title, query_str) == False)
                       & (Match(Post.content, query_str) == False))



    else:
        posts_matched_content = Post.select()\
                .where((Post.published == True)
                       & (Match(Post.content, query_str) == True))
        posts_matched_title = Post.select()\
                .where((Post.published == True)
                       & (Match(Post.title, query_str) == True)
                       & (Match(Post.content, query_str) == False))
        posts_matched_tag = Post.select().join(PostTag).join(Tag) \
                .where((Post.published == True)
                       & (Match(Tag.name, query_str) == True)
                       & (Match(Post.title, query_str) == False)
                       & (Match(Post.content, query_str) == False))

    posts_matched = posts_matched_content + posts_matched_title + posts_matched_tag

    number_of_matched_posts = posts_matched.count()

    posts_matched = posts_matched.paginate(page, settings.posts_per_page)

    posts_with_tags = []
    for post in posts_matched:
        tags = Tag.select().join(PostTag)\
            .where(PostTag.post == post).order_by(Tag.name)
        posts_with_tags.append([post, tags])

    pages = Pagination(page, settings.posts_per_page, number_of_matched_posts, 7)

    if not number_of_matched_posts == 0:
        return render_template('search_view.html',
                               posts_with_tags=posts_with_tags,
                               pages=pages,
                               query=query,
                               current=search_view)

    else:
        notice = "No search results for " + str(query_str) + " !"
        return render_template('notice.html', notice=notice)


# Preview a post below the compose view
@app.route('/admin/preview', methods=["POST"])
@login_required
@admin_required
def preview():
    data = request.get_json()
    html = markdown.markdown(data['postContent_markdown'], extensions=[GithubMarkdown()])
    date_time = datetime.datetime.now().strftime("%B %d, %Y")
    return jsonify(html=html, date_time=date_time)

# View to create a post
@app.route('/admin/posts/compose')
@login_required
@admin_required
def compose():
    all_tags = Tag.select()
    return render_template('compose.html', editing=False, all_tags=all_tags)

# Edit a post via the compose view
@app.route('/admin/posts/edit/<pid>')
@login_required
@admin_required
def admin_edit_post(pid):
    post = None

    try:
        post = Post.get(pid == Post.id)
        tags_of_post = Tag.select().join(PostTag).join(Post)\
            .where(Post.id == post.id).order_by(Tag.name)
        all_tags = Tag.select()
    except Post.DoesNotExist:
        abort(404)

    return render_template('compose.html',
                           editing=True,
                           pid=pid,
                           post=post,
                           tags_of_post=tags_of_post,
                           all_tags=all_tags)

# Save a created or edited post
@app.route('/admin/posts/save', methods=["POST"])
@login_required
@admin_required
def admin_save_post():

    edit_id = request.form.get('post-edit-id')
    title = request.form.get('post-form-title')
    slug = util.slugify(title)
    content = request.form.get('post-form-content')
    description = request.form.get('post-form-description')
    tags = request.form.get('post-form-tags')
    publish = request.form.get('post-form-publish')

    tags = [tag_json["value"] for tag_json in json.loads(tags)] if tags else None
    publish = True if publish == 'on' else False

    if title or content or description:
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

                if tags is not None:
                    for tag_name in tags:
                        tag, _ = Tag.get_or_create(name=tag_name)
                        posttag, _ = PostTag.get_or_create(post=post, tag=tag)

                old_tags = Tag.select().join(PostTag).join(Post).where(Post == post).order_by(Tag.name)
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

                if tags is not None:
                    for tag_name in tags:
                        tag, _ = Tag.get_or_create(name=tag_name)
                        posttag, _ = PostTag.get_or_create(post=post, tag=tag)

                if publish:
                    flash("Post published!", "success")
                elif not publish:
                    flash("Post saved as draft!", "success")

            except peewee.IntegrityError:
                print("peewee.IntegrityError")
                abort(400)
    else:
        flash("Empty post", "danger")

    return redirect(url_for('admin_post_list'))

# 'Index' view of the admin part of the app
@app.route('/admin')
@login_required
@admin_required
def admin_main():
    return redirect(url_for('admin_post_list'))

# Table view of all posts
@app.route('/admin/posts')
@login_required
@admin_required
def admin_post_list():
    posts = Post.select()

    posts_with_user_and_tags = []
    for post in posts:
        tags = Tag.select().join(PostTag).join(Post).where(Post.id == post.id).order_by(Tag.name)
        user = User.select().join(PostUser, peewee.JOIN.LEFT_OUTER).where(PostUser.post == post)
        if user:
            user = user[0]  # Accessing the first (and only) result of the query... if a postuser existed
        posts_with_user_and_tags.append([post, user, tags])

    posts_with_user_and_tags = sorted(posts_with_user_and_tags,
                                      key=lambda post_with_user_and_tag: post_with_user_and_tag[0].updated_at,
                                      reverse=True)

    return render_template('post_list.html', posts_with_user_and_tags=posts_with_user_and_tags)


    # Legacy sort code to use if list js isnt wanted anymore
    #order_by = request.args.get('order_by')
    #order = request.args.get('order')
    #if (order_by == 'title' and order == 'asc' ):
    #    posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[0].title.lower() )
    #elif(order_by == 'title' and order == 'desc' ):
    #    posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[0].title.lower(), reverse=True )
    #elif (order_by == 'user' and order == 'asc'):
    #    posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[1].name.lower() )
    #elif (order_by == 'user' and order == 'desc'):
    #    posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[1].name.lower(), reverse=True )
    #elif (order_by == 'updated_at' and order == 'asc'):
    #    posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[0].updated_at )
    #else:
    #    posts_with_user_and_tags = sorted(posts_with_user_and_tags, key=lambda post_with_user_and_tag: post_with_user_and_tag[0].updated_at, reverse=True )
    #    order_by = 'updated_at'
    #    order = 'desc'


# Delete a post
@app.route('/admin/posts/delete', methods=["POST"])
@login_required
@admin_required
def admin_post_delete():
    status = {'ok': True}

    data = request.get_json()
    if 'id' not in data:
        abort(400)

    id_to_delete = data["id"]

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


# Table view of all tags - number of tagged posts with link to blog view of these posts
@app.route('/admin/tags')
@login_required
@admin_required
def admin_tag_list():
    tags_with_post_counts = Tag.select(Tag, fn.Count(Post.id).alias('count')) \
        .join(PostTag, peewee.JOIN.LEFT_OUTER) \
        .join(Post, peewee.JOIN.LEFT_OUTER) \
        .group_by(Tag) \
        .limit(20)
    tags_with_post_counts = sorted(tags_with_post_counts,
           key=lambda tags_with_post_counts: tags_with_post_counts.updated_at,
           reverse=True)
    return render_template('tag_list.html', tags=tags_with_post_counts)


@app.route('/admin/tags/create')
@login_required
@admin_required
def admin_tag_create():
    all_tags = Tag.select()
    return render_template('tag_edit.html', editing=False, tags=False, all_tags = all_tags)


@app.route('/admin/tags/edit/<uid>')
@login_required
@admin_required
def admin_tag_edit(uid):
    try:
        tag_to_edit = Tag.get(Tag.id == uid)
        all_tags = Tag.select().where(Tag.id != tag_to_edit.id)
    except Tag.DoesNotExist:
        abort(404)
    return render_template('tag_edit.html', editing=True, tag_to_edit=tag_to_edit, all_tags = all_tags )


@app.route('/admin/tags/save', methods=["POST"])
@login_required
@admin_required
def admin_tag_save():

    tags = request.form.get('tags')
    edit_id = request.form.get('tag-edit-id')

    tags = [tag_json["value"] for tag_json in json.loads(tags)] if tags else None
    if tags:
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
    else:
        flash("No tag names", "danger")
    return redirect(url_for('admin_tag_list'))


@app.route('/admin/tags/delete', methods=["POST"])
@login_required
@admin_required
def admin_tag_delete():
    status = {'ok': True}

    data = request.get_json()
    if 'id' not in data:
        abort(400)

    id_to_delete = data["id"]

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
    return render_template('user_edit.html', editing=False, selfediting=False)


@app.route('/admin/users/edit/<uid>')
@login_required
@admin_required
def user_edit(uid):
    try:
        user_to_edit = User.get(User.id == uid)
    except User.DoesNotExist:
        abort(404)

    if user_to_edit.id == current_user.id:
        return render_template('user_edit.html', editing=True, user=user_to_edit, selfediting=True)
    else:
        return render_template('user_edit.html', editing=True, user=user_to_edit, selfediting=False)


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

    if username and password:
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

    else:
        flash("Can't create user without name and password", "danger")

    if current_user.admin:
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


def user_delete(uid):

    status = {'ok': True}

    id_to_delete = uid
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

@app.route('/profile/delete', methods=["POST"])
@login_required
def profile_user_delete():

    data = request.get_json()
    if 'id' not in data:
        abort(400)
    id_to_delete = data["id"]

    if id_to_delete == current_user.id:
        return user_delete(id_to_delete)
    elif id_to_delete != current_user.id:
        flash("You only can delete yourself!")
        abort(400)


@app.route('/admin/users/delete', methods=["POST"])
@login_required
@admin_required
def admin_user_delete():

    data = request.get_json()
    if 'id' not in data:
        abort(400)
    id_to_delete = data["id"]

    if id_to_delete == current_user.id:
        status = {'ok': False}
        flash(
            "You can't delete yourself via this table. If you are sure you wan't to delete yourself, please use the \
             delete option in your profile,",
            "danger")
        return json.dumps(status)

    elif id_to_delete != current_user.id:
        return user_delete(id_to_delete)


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
        current_settings.max_synopsis_chars = request.form.get('max-synopsis-chars')
        current_settings.table_entries_per_page = request.form.get('table-entries-per-page')
        current_settings.save()

        flash("Settings updated.", "success")
    except Settings.DoesNotExist:
        flash("Please try again.", "danger")

    return redirect(url_for('admin_settings'))


@app.errorhandler(404)
def page_not_found(e):
    notice = """404: Nothing to see here!"""
    return render_template('notice.html', notice=notice), 404

@app.errorhandler(400)
def bad_request(e):
    notice = """400: Bad request!"""
    return render_template('notice.html', notice=notice), 400

@app.errorhandler(DatabaseError)
def special_exception_handler(error):
    notice = """500: Something went wrong!"""
    return render_template('notice.html', notice=notice), 500


if __name__ == '__main__':
    app.debug = True
    app.run()

