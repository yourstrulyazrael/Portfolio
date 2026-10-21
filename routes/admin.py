from flask import Blueprint, render_template, session, redirect, url_for, flash, request, abort
from database import supabase, bucket, first
from routes.common import (
    PROJECT_IMAGE_FOLDER, CERTIFICATE_FOLDER,
    list_projects, get_project, list_certificates, list_messages, shape_certificate,
)
import mimetypes
import os
import uuid
from werkzeug.utils import secure_filename


admin = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
CERTIFICATE_EXTENSIONS = ALLOWED_EXTENSIONS | {"pdf"}


def allowed_file(filename, extensions=ALLOWED_EXTENSIONS):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions


def save_upload(file, folder):
    """Upload a file to the Storage bucket under <folder>/ with a random name and return that name."""
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
    """Return the non-empty files from a multi-file input, or None if any has an invalid type."""
    images = [image for image in request.files.getlist(field) if image and image.filename]
    if any(not allowed_file(image.filename) for image in images):
        return None
    return images


def get_technology_options(assigned_ids=()):
    """Technologies offered on the project form: one per skill, plus any the project is already tagged with."""
    skills = supabase.table("skills").select("name, category").order("category").execute().data
    technologies = supabase.table("technologies").select("id, name").execute().data

    # Names are case-insensitive (citext); the alphabetically first category wins for duplicates
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
    """A URL from the form, or None if left blank. Returns False if it isn't an http(s) link,
    so values like javascript: never end up in an href."""
    value = request.form.get(field, "").strip()
    if not value:
        return None
    return value if value.lower().startswith(("http://", "https://")) else False


def read_project_form():
    """The project's text fields, or None (after flashing why) if a link is invalid."""
    github_url = read_url("github_url")
    live_url = read_url("live_url")

    if github_url is False or live_url is False:
        flash("Links must start with http:// or https://", "danger")
        return None

    return {
        "title": request.form["title"],
        "description": request.form["description"],
        "github_url": github_url,
        "live_url": live_url,
        "demo_credentials": read_demo_credentials(),
    }


MAX_DEMO_ACCOUNTS = 10


def read_demo_credentials():
    """Demo logins from the repeating form rows, skipping rows with no username and no password."""
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

    return render_template("admin.html", projects = projects, skills = skills, certificates = certificates, messages = messages)

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

        project = supabase.table("projects").insert(fields).execute().data[0]

        set_project_technologies(project["id"], technology_ids)
        add_project_images(project["id"], images)

        flash("Project added successfully!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template(
        "add_project.html",
        technologies=technologies
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

        supabase.table("projects").update(fields).eq("id", project_id).execute()

        set_project_technologies(project_id, technology_ids)

        # Remove ticked images, then renumber the rest with the chosen cover first
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
        images=images
    )

@admin.route('/admin/delete-project/<int:project_id>', methods=["POST"])
def delete_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    project = get_project(project_id)

    if project is None:
        abort(404)

    # project_images and project_technologies rows are removed by ON DELETE CASCADE
    supabase.table("projects").delete().eq("id", project_id).execute()

    delete_uploads([image["filename"] for image in project["images"]], PROJECT_IMAGE_FOLDER)

    flash("Project deleted successfully!", "success")
    return redirect(url_for("admin.dashboard"))


def read_certificate_form():
    """The certificate's text fields, or None (after flashing why) if the link is invalid."""
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
    """Keep the technologies table in step with skill names so every skill can be tagged on a project.

    Renaming a skill renames its technology too (so projects already tagged with it follow along),
    unless another skill still uses the old name or the new name already exists as a technology.
    Names are citext columns, so eq() comparisons are case-insensitive.
    """
    if old_name and old_name.lower() != new_name.lower():
        old_still_used = bool(supabase.table("skills").select("id").eq("name", old_name).limit(1).execute().data)
        new_exists = bool(supabase.table("technologies").select("id").eq("name", new_name).limit(1).execute().data)

        if not old_still_used and not new_exists:
            supabase.table("technologies").update({"name": new_name}).eq("name", old_name).execute()
        else:
            remove_unused_technology(old_name)
    elif old_name:
        # Only the capitalisation changed
        supabase.table("technologies").update({"name": new_name}).eq("name", old_name).execute()

    supabase.table("technologies").upsert(
        {"name": new_name}, on_conflict="name", ignore_duplicates=True
    ).execute()


def remove_unused_technology(name):
    """Delete a technology once no skill has its name and no project is tagged with it."""
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
    # Projects already tagged with it keep the technology
    remove_unused_technology(skill["name"])

    flash("Skill deleted successfully!", "success")
    return redirect(url_for('admin.dashboard'))

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
