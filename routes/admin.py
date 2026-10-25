from flask import Blueprint, render_template, session, redirect, url_for, flash, request, abort, g
from database import supabase, bucket, first
from routes.auth import (
    get_user, password_problems, password_fingerprint, start_session, USERNAME_PATTERN, MIN_PASSWORD_LENGTH,
)
from werkzeug.security import check_password_hash, generate_password_hash
from routes.common import (
    PROJECT_IMAGE_FOLDER, CERTIFICATE_FOLDER, PROFILE_FOLDER, PROJECT_STATUSES,
    list_projects, get_project, list_certificates, list_messages, shape_certificate,
    get_site_settings, get_profile, list_testimonials, THEMES, ACCENTS,
)
from datetime import datetime, timezone
import mimetypes
import os
import uuid
from werkzeug.utils import secure_filename


admin = Blueprint("admin", __name__)


@admin.before_request
def require_admin():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = get_user(id=session["user_id"])
    if user is None or session.get("pw") != password_fingerprint(user["password"]):
        session.clear()
        flash("Please sign in again.", "warning")
        return redirect(url_for("auth.login"))
    g.admin_user = user

    if session.get("must_change_password") and request.endpoint != "admin.account":
        flash("Set a new password before using the dashboard.", "warning")
        return redirect(url_for("admin.account"))


@admin.route("/admin/account", methods=["GET", "POST"])
def account():
    user = g.admin_user
    must_change = bool(session.get("must_change_password"))

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        username = request.form.get("username", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(user["password"], current_password):
            flash("Your current password is incorrect.", "danger")
            return redirect(url_for("admin.account"))

        problems = []
        if not USERNAME_PATTERN.match(username):
            problems.append("Usernames are 3-50 letters, numbers, dots, dashes or underscores.")
        elif username.lower() != user["username"].lower() and get_user(username=username):
            problems.append("That username is already taken.")

        if must_change and not new_password:
            problems.append("Choose a new password.")
        if new_password:
            problems += password_problems(new_password, username)
            if new_password != confirm_password:
                problems.append("The new passwords don't match.")
            if check_password_hash(user["password"], new_password):
                problems.append("Choose a password that's different from the current one.")

        if problems:
            for problem in problems:
                flash(problem, "danger")
            return redirect(url_for("admin.account"))

        fields = {"username": username}
        if new_password:
            fields["password"] = generate_password_hash(new_password)
        supabase.table("users").update(fields).eq("id", user["id"]).execute()

        start_session(get_user(id=user["id"]))
        flash("Account updated." + (" Any other signed-in devices have been signed out." if new_password else ""), "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("account.html", user=user, must_change=must_change, min_length=MIN_PASSWORD_LENGTH)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
CERTIFICATE_EXTENSIONS = ALLOWED_EXTENSIONS | {"pdf"}


def allowed_file(filename, extensions=ALLOWED_EXTENSIONS):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions


def save_upload(file, folder):
    extension = os.path.splitext(secure_filename(file.filename))[1].lower()
    filename = f"{uuid.uuid4().hex}{extension}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    bucket().upload(f"{folder}/{filename}", file.read(), {"content-type": content_type})
    return filename


def delete_uploads(filenames, folder):
    paths = [f"{folder}/{filename}" for filename in filenames if filename]
    if paths:
        bucket().remove(paths)


def get_uploaded_images(field):
    images = [image for image in request.files.getlist(field) if image and image.filename]
    if any(not allowed_file(image.filename) for image in images):
        return None
    return images


def get_technology_options(assigned_ids=()):
    skills = supabase.table("skills").select("name, category").order("category").execute().data
    technologies = supabase.table("technologies").select("id, name").execute().data

    category_by_name = {}
    for skill in skills:
        category_by_name.setdefault(skill["name"].lower(), skill["category"])

    options = [
        {**technology, "category": category_by_name.get(technology["name"].lower(), "Other")}
        for technology in technologies
        if technology["name"].lower() in category_by_name or technology["id"] in assigned_ids
    ]
    options.sort(key=lambda option: (option["category"] == "Other", option["category"], option["name"].lower()))
    return options


def read_url(field):
    value = request.form.get(field, "").strip()
    if not value:
        return None
    return value if value.lower().startswith(("http://", "https://")) else False


def read_project_form():
    github_url = read_url("github_url")
    live_url = read_url("live_url")

    if github_url is False or live_url is False:
        flash("Links must start with http:// or https://", "danger")
        return None

    status = request.form.get("status", "completed")

    return {
        "title": request.form["title"],
        "description": request.form["description"],
        "github_url": github_url,
        "live_url": live_url,
        "demo_credentials": read_demo_credentials(),
        "role": read_text("role", 150),
        "problem": read_text("problem"),
        "solution": read_text("solution"),
        "features": read_text("features"),
        "challenges": read_text("challenges"),
        "status": status if status in PROJECT_STATUSES else "completed",
        "started_on": read_month("started_on"),
        "finished_on": read_month("finished_on"),
        "featured": bool(request.form.get("featured")),
        "sort_order": request.form.get("sort_order", 0, type=int) or 0,
    }


def read_text(field, max_length=5000):
    return request.form.get(field, "").strip()[:max_length] or None


def read_month(field):
    value = request.form.get(field, "").strip()
    if len(value) == 7 and value[:4].isdigit() and value[4] == "-" and value[5:].isdigit():
        return f"{value}-01"
    return None


CASE_STUDY_FIELDS = ("role", "problem", "solution", "features", "challenges",
                     "status", "started_on", "finished_on", "featured", "sort_order")


def write_project(fields, project_id=None):
    def run(values):
        table = supabase.table("projects")
        query = table.update(values).eq("id", project_id) if project_id else table.insert(values)
        return query.execute().data

    try:
        return run(fields)
    except Exception as error:
        if "column" not in str(error).lower():
            raise
        flash("Saved, except the case-study fields: run supabase/schema.sql again in the "
              "Supabase SQL Editor to enable them.", "warning")
        return run({key: value for key, value in fields.items() if key not in CASE_STUDY_FIELDS})


MAX_DEMO_ACCOUNTS = 10


def read_demo_credentials():
    rows = zip(
        request.form.getlist("demo_label"),
        request.form.getlist("demo_username"),
        request.form.getlist("demo_password"),
    )
    credentials = []
    for label, username, password in rows:
        label, username, password = label.strip()[:50], username.strip()[:150], password.strip()[:150]
        if username or password:
            credentials.append({"label": label, "username": username, "password": password})
    return credentials[:MAX_DEMO_ACCOUNTS]


def read_technology_ids():
    return [int(technology_id) for technology_id in request.form.getlist("technologies")]


def set_project_technologies(project_id, technology_ids):
    supabase.table("project_technologies").delete().eq("project_id", project_id).execute()
    if technology_ids:
        supabase.table("project_technologies").insert(
            [{"project_id": project_id, "technology_id": technology_id} for technology_id in technology_ids]
        ).execute()


def add_project_images(project_id, images, start=0):
    rows = [
        {"project_id": project_id, "filename": save_upload(image, PROJECT_IMAGE_FOLDER), "sort_order": position}
        for position, image in enumerate(images, start=start)
    ]
    if rows:
        supabase.table("project_images").insert(rows).execute()


@admin.route('/admin')
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    projects = list_projects()
    skills = supabase.table("skills").select("*").order("id").execute().data
    certificates = list_certificates()
    messages = list_messages()

    return render_template(
        "admin.html", projects = projects, skills = skills, certificates = certificates, messages = messages,
        testimonials = list_testimonials(),
    )

@admin.route('/admin/add-project', methods=["GET", "POST"])
def add_project():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    technologies = get_technology_options()

    if request.method == "POST":
        fields = read_project_form()
        technology_ids = read_technology_ids()
        images = get_uploaded_images("images")

        if fields is None:
            return redirect(url_for("admin.add_project"))

        if images is None:
            flash("Invalid image type. Use PNG, JPG, JPEG or WEBP.", "danger")
            return redirect(url_for("admin.add_project"))

        project = write_project(fields)[0]

        set_project_technologies(project["id"], technology_ids)
        add_project_images(project["id"], images)

        flash("Project added successfully!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template(
        "add_project.html",
        technologies=technologies,
        statuses=PROJECT_STATUSES,
    )

@admin.route('/admin/edit-project/<int:project_id>', methods=["GET", "POST"])
def edit_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    project = get_project(project_id)

    if project is None:
        abort(404)

    assigned_ids = {technology["id"] for technology in project["technology_list"]}
    technologies = get_technology_options(assigned_ids)
    images = project["images"]

    if request.method == "POST":
        fields = read_project_form()
        technology_ids = read_technology_ids()
        new_images = get_uploaded_images("images")
        remove_ids = {int(image_id) for image_id in request.form.getlist("remove_images")}
        cover_id = request.form.get("cover_image", type=int)

        if fields is None:
            return redirect(url_for("admin.edit_project", project_id = project_id))

        if new_images is None:
            flash("Invalid image type. Use PNG, JPG, JPEG or WEBP.", "danger")
            return redirect(url_for("admin.edit_project", project_id = project_id))

        write_project(fields, project_id)

        set_project_technologies(project_id, technology_ids)

        removed = [image for image in images if image["id"] in remove_ids]
        kept_images = [image for image in images if image["id"] not in remove_ids]

        if removed:
            supabase.table("project_images").delete().in_("id", [image["id"] for image in removed]).execute()
            delete_uploads([image["filename"] for image in removed], PROJECT_IMAGE_FOLDER)

        kept_images.sort(key=lambda image: image["id"] != cover_id)

        for position, image in enumerate(kept_images):
            if image["sort_order"] != position:
                supabase.table("project_images").update({"sort_order": position}).eq("id", image["id"]).execute()

        add_project_images(project_id, new_images, start=len(kept_images))

        flash("Project updated successfully!", "success")

        return redirect(url_for("admin.dashboard"))

    return render_template(
        "edit_project.html",
        project=project,
        technologies=technologies,
        assigned_technologies=[{"technology_id": technology_id} for technology_id in assigned_ids],
        images=images,
        statuses=PROJECT_STATUSES,
    )

@admin.route('/admin/delete-project/<int:project_id>', methods=["POST"])
def delete_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    project = get_project(project_id)

    if project is None:
        abort(404)

    supabase.table("projects").delete().eq("id", project_id).execute()

    delete_uploads([image["filename"] for image in project["images"]], PROJECT_IMAGE_FOLDER)

    flash("Project deleted successfully!", "success")
    return redirect(url_for("admin.dashboard"))


def read_certificate_form():
    credential_url = read_url("credential_url")

    if credential_url is False:
        flash("The credential URL must start with http:// or https://", "danger")
        return None

    return {
        "title": request.form["title"],
        "issuer": request.form["issuer"],
        "issue_date": request.form.get("issue_date") or None,
        "credential_url": credential_url,
        "description": request.form.get("description") or None,
    }


def get_certificate(certificate_id):
    certificate = first(supabase.table("certificates").select("*").eq("id", certificate_id).execute())
    return shape_certificate(certificate) if certificate else None


@admin.route('/admin/add-certificate', methods=["GET", "POST"])
def add_certificate():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        fields = read_certificate_form()
        file = request.files.get("file")
        filename = None

        if fields is None:
            return redirect(url_for("admin.add_certificate"))

        if file and file.filename:
            if not allowed_file(file.filename, CERTIFICATE_EXTENSIONS):
                flash("Invalid file type. Use PNG, JPG, JPEG, WEBP or PDF.", "danger")
                return redirect(url_for("admin.add_certificate"))
            filename = save_upload(file, CERTIFICATE_FOLDER)

        supabase.table("certificates").insert({**fields, "file": filename}).execute()

        flash("Certificate added successfully!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("add_certificate.html")

@admin.route('/admin/edit-certificate/<int:certificate_id>', methods=["GET", "POST"])
def edit_certificate(certificate_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    certificate = get_certificate(certificate_id)

    if certificate is None:
        abort(404)

    if request.method == "POST":
        fields = read_certificate_form()
        file = request.files.get("file")
        filename = certificate["file"]

        if fields is None:
            return redirect(url_for("admin.edit_certificate", certificate_id = certificate_id))

        if file and file.filename:
            if not allowed_file(file.filename, CERTIFICATE_EXTENSIONS):
                flash("Invalid file type. Use PNG, JPG, JPEG, WEBP or PDF.", "danger")
                return redirect(url_for("admin.edit_certificate", certificate_id = certificate_id))
            filename = save_upload(file, CERTIFICATE_FOLDER)
            delete_uploads([certificate["file"]], CERTIFICATE_FOLDER)
        elif request.form.get("remove_file"):
            delete_uploads([certificate["file"]], CERTIFICATE_FOLDER)
            filename = None

        supabase.table("certificates").update(
            {**fields, "file": filename}
        ).eq("id", certificate_id).execute()

        flash("Certificate updated successfully!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("edit_certificate.html", certificate = certificate)

@admin.route('/admin/delete-certificate/<int:certificate_id>', methods=["POST"])
def delete_certificate(certificate_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    certificate = get_certificate(certificate_id)

    if certificate is None:
        abort(404)

    supabase.table("certificates").delete().eq("id", certificate_id).execute()
    delete_uploads([certificate["file"]], CERTIFICATE_FOLDER)

    flash("Certificate deleted successfully!", "success")
    return redirect(url_for("admin.dashboard"))


def sync_skill_technology(new_name, old_name=None):

    if old_name and old_name.lower() != new_name.lower():
        old_still_used = bool(supabase.table("skills").select("id").eq("name", old_name).limit(1).execute().data)
        new_exists = bool(supabase.table("technologies").select("id").eq("name", new_name).limit(1).execute().data)

        if not old_still_used and not new_exists:
            supabase.table("technologies").update({"name": new_name}).eq("name", old_name).execute()
        else:
            remove_unused_technology(old_name)
    elif old_name:
        supabase.table("technologies").update({"name": new_name}).eq("name", old_name).execute()

    supabase.table("technologies").upsert(
        {"name": new_name}, on_conflict="name", ignore_duplicates=True
    ).execute()


def remove_unused_technology(name):
    technology = first(supabase.table("technologies").select("id").eq("name", name).limit(1).execute())
    if technology is None:
        return

    if supabase.table("skills").select("id").eq("name", name).limit(1).execute().data:
        return

    if supabase.table("project_technologies").select("project_id").eq("technology_id", technology["id"]).limit(1).execute().data:
        return

    supabase.table("technologies").delete().eq("id", technology["id"]).execute()


@admin.route('/admin/add-skill', methods = ["GET", "POST"])
def add_skill():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        name = request.form["name"].strip()
        category = request.form["category"].strip()
        proficiency = request.form["proficiency"].strip()

        supabase.table("skills").insert({"name": name, "category": category, "proficiency": proficiency}).execute()
        sync_skill_technology(name)

        flash("Skill added successfully!", "success")
        return redirect(url_for('admin.dashboard'))
    return render_template("add_skill.html")

@admin.route('/admin/edit-skill/<int:skill_id>', methods = ["GET", "POST"])
def edit_skill(skill_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    skill = first(supabase.table("skills").select("*").eq("id", skill_id).execute())

    if skill is None:
        abort(404)

    if request.method == "POST":
        name = request.form["name"].strip()
        category = request.form["category"].strip()
        proficiency = request.form["proficiency"].strip()

        supabase.table("skills").update(
            {"name": name, "category": category, "proficiency": proficiency}
        ).eq("id", skill_id).execute()
        sync_skill_technology(name, old_name = skill["name"])

        flash("Skill updated successfully!", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("edit_skill.html", skill = skill)

@admin.route('/admin/delete-skill/<int:skill_id>', methods = ["POST"])
def delete_skill(skill_id):
    if "user_id" not in session:
        return redirect(url_for('auth.login'))

    skill = first(supabase.table("skills").select("name").eq("id", skill_id).execute())

    if skill is None:
        abort(404)

    supabase.table("skills").delete().eq("id", skill_id).execute()
    remove_unused_technology(skill["name"])

    flash("Skill deleted successfully!", "success")
    return redirect(url_for('admin.dashboard'))

@admin.route('/admin/appearance', methods=["GET", "POST"])
def appearance():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        theme = request.form.get("theme")
        accent = request.form.get("accent")

        if theme not in THEMES or accent not in ACCENTS:
            flash("Pick one of the listed themes and accents.", "danger")
            return redirect(url_for("admin.appearance"))

        try:
            supabase.table("site_settings").upsert(
                {"id": 1, "theme": theme, "accent": accent, "updated_at": datetime.now(timezone.utc).isoformat()},
                on_conflict="id",
            ).execute()
        except Exception:
            flash("Couldn't save. Run supabase/schema.sql again in the Supabase SQL Editor first.", "danger")
            return redirect(url_for("admin.appearance"))

        flash("Appearance saved. New visitors will see these defaults.", "success")
        return redirect(url_for("admin.appearance"))

    return render_template("appearance.html", settings = get_site_settings(), themes = THEMES)

@admin.route("/admin/messages")
def messages():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    messages = list_messages()

    return render_template("messages.html", messages=messages)

@admin.route('/admin/delete-messages/<int:message_id>', methods = ["POST"])
def delete_message(message_id):
    if "user_id" not in session:
        return redirect(url_for('auth.login'))

    supabase.table("messages").delete().eq("id", message_id).execute()

    flash("Message deleted successfully!", "success")

    return redirect(url_for('admin.messages'))


PROFILE_TEXT_FIELDS = {
    "full_name": 100, "headline": 150, "location": 100, "email": 255, "availability": 150, "bio": 5000,
}
PROFILE_LINK_FIELDS = ("github_url", "linkedin_url", "website_url")


@admin.route("/admin/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        fields = {field: read_text(field, length) for field, length in PROFILE_TEXT_FIELDS.items()}
        for field in PROFILE_LINK_FIELDS:
            fields[field] = read_url(field)
        if any(fields[field] is False for field in PROFILE_LINK_FIELDS):
            flash("Links must start with http:// or https://", "danger")
            return redirect(url_for("admin.profile"))
        if fields["email"] and "@" not in fields["email"]:
            flash("Enter a valid email address.", "danger")
            return redirect(url_for("admin.profile"))

        try:
            current = first(supabase.table("profile").select("cv_file").eq("id", 1).limit(1).execute()) or {}
        except Exception:
            flash("Couldn't save. Run supabase/schema.sql again in the Supabase SQL Editor first.", "danger")
            return redirect(url_for("admin.profile"))

        cv_file = current.get("cv_file")
        upload = request.files.get("cv")
        if upload and upload.filename:
            if not allowed_file(upload.filename, {"pdf"}):
                flash("The CV must be a PDF.", "danger")
                return redirect(url_for("admin.profile"))
            new_file = save_upload(upload, PROFILE_FOLDER)
            delete_uploads([cv_file], PROFILE_FOLDER)
            cv_file = new_file
        elif request.form.get("remove_cv") and cv_file:
            delete_uploads([cv_file], PROFILE_FOLDER)
            cv_file = None

        supabase.table("profile").upsert(
            {"id": 1, **fields, "cv_file": cv_file, "updated_at": datetime.now(timezone.utc).isoformat()},
            on_conflict="id",
        ).execute()

        flash("Profile saved.", "success")
        return redirect(url_for("admin.profile"))

    try:
        saved = first(supabase.table("profile").select("*").eq("id", 1).limit(1).execute()) or {}
        table_ready = True
    except Exception:
        saved, table_ready = {}, False

    return render_template("profile.html", saved=saved, table_ready=table_ready)


def read_testimonial_form():
    link_url = read_url("link_url")
    if link_url is False:
        flash("The link must start with http:// or https://", "danger")
        return None

    fields = {
        "name": read_text("name", 100),
        "role": read_text("role", 150),
        "quote": read_text("quote", 2000),
        "link_url": link_url,
        "sort_order": request.form.get("sort_order", 0, type=int) or 0,
    }
    if not fields["name"] or not fields["quote"]:
        flash("A name and a quote are required.", "danger")
        return None
    return fields


@admin.route("/admin/add-testimonial", methods=["GET", "POST"])
def add_testimonial():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        fields = read_testimonial_form()
        if fields is None:
            return redirect(url_for("admin.add_testimonial"))
        try:
            supabase.table("testimonials").insert(fields).execute()
        except Exception:
            flash("Couldn't save. Run supabase/schema.sql again in the Supabase SQL Editor first.", "danger")
            return redirect(url_for("admin.add_testimonial"))

        flash("Testimonial added successfully!", "success")
        return redirect(url_for("admin.dashboard") + "#testimonials")

    return render_template("testimonial_form.html", testimonial=None)


@admin.route("/admin/edit-testimonial/<int:testimonial_id>", methods=["GET", "POST"])
def edit_testimonial(testimonial_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    testimonial = first(supabase.table("testimonials").select("*").eq("id", testimonial_id).execute())
    if testimonial is None:
        abort(404)

    if request.method == "POST":
        fields = read_testimonial_form()
        if fields is None:
            return redirect(url_for("admin.edit_testimonial", testimonial_id=testimonial_id))
        supabase.table("testimonials").update(fields).eq("id", testimonial_id).execute()

        flash("Testimonial updated successfully!", "success")
        return redirect(url_for("admin.dashboard") + "#testimonials")

    return render_template("testimonial_form.html", testimonial=testimonial)


@admin.route("/admin/delete-testimonial/<int:testimonial_id>", methods=["POST"])
def delete_testimonial(testimonial_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    supabase.table("testimonials").delete().eq("id", testimonial_id).execute()

    flash("Testimonial deleted successfully!", "success")
    return redirect(url_for("admin.dashboard") + "#testimonials")
