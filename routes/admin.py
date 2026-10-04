from flask import Blueprint, render_template, session, redirect, url_for, flash, request, abort
from database import db
import os
import uuid
from werkzeug.utils import secure_filename


admin = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@admin.route('/admin')
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            projects.id,
            projects.title,
            projects.description,
            GROUP_CONCAT(technologies.name SEPARATOR ', ') AS technologies
            FROM projects
            LEFT JOIN project_technologies
                ON projects.id = project_technologies.project_id
            LEFT JOIN technologies
                ON project_technologies.technology_id = technologies.id
        
            GROUP BY projects.id
        """)
    projects = cursor.fetchall()

    cursor.execute("SELECT * FROM skills")
    skills = cursor.fetchall()

    cursor.execute("SELECT * FROM messages ORDER BY created_at DESC")
    messages = cursor.fetchall()

    cursor.close()


    return render_template("admin.html", projects = projects, skills = skills, messages = messages)

@admin.route('/admin/add-project', methods=["GET", "POST"])
def add_project():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM technologies ORDER BY name")

    technologies = cursor.fetchall()
    cursor.close()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        github_url = request.form["github_url"]
        technology_ids = request.form.getlist("technologies")
        image = request.files.get("image")

        filename = None

        if image and image.filename:
            if not allowed_file(image.filename):
                flash("Invalid image type.", "error")
                return redirect(url_for("admin.add_project"))

            original_filename = secure_filename(image.filename)
            extension = os.path.splitext(original_filename)[1].lower()

            filename = f"{uuid.uuid4().hex}{extension}"
            image.save("static/images/projects/" + filename)

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO projects (title, description, github_url, image)
            VALUES (%s, %s, %s, %s)
        """, (title, description, github_url, filename))

        project_id = cursor.lastrowid

        for technology_id in technology_ids:
            cursor.execute("""
                INSERT INTO project_technologies (project_id, technology_id)
                VALUES (%s, %s)
            """, (project_id, technology_id))

        db.commit()
        cursor.close()

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

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()

    cursor.execute("SELECT * FROM technologies ORDER BY name")
    technologies = cursor.fetchall()

    cursor.execute("""
        SELECT technology_id
        FROM project_technologies
        WHERE project_id = %s
    """, (project_id,))

    assigned_technologies = cursor.fetchall()
    cursor.close()

    if project is None:
        abort(404)

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        github_url = request.form["github_url"]
        technology_ids = request.form.getlist("technologies")
        image = request.files.get("image")

        if image and image.filename:
            if not allowed_file(image.filename):
                flash("Invalid image type.", "danger    ")
                return redirect(url_for("admin.edit_project", project_id = project_id))

            original_filename = secure_filename(image.filename)
            extension = os.path.splitext(original_filename)[1].lower()

            filename = f'{uuid.uuid4().hex}{extension}'
            old_image = project["image"]
            image.save("static/images/projects/" + filename)

            if old_image:
                old_image_path = os.path.join("static/images/projects", old_image)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)

        cursor = db.cursor()

        if image and image.filename:
            cursor.execute("""
                UPDATE projects
                SET title = %s,
                    description = %s,
                    github_url = %s,
                    image = %s
                WHERE id = %s
            """, (title, description, github_url, filename, project_id))

        else:
            cursor.execute("""
                UPDATE projects
                SET title = %s,
                    description = %s,
                    github_url = %s
                WHERE id = %s
            """, (title, description, github_url, project_id))

        cursor.execute(
            "DELETE FROM project_technologies WHERE project_id = %s",
            (project_id,)
        )

        for technology_id in technology_ids:
            cursor.execute("""
                INSERT INTO project_technologies(project_id, technology_id)
                VALUES(%s, %s)
            """, (project_id, technology_id))

        db.commit()
        cursor.close()

        flash("Project updated successfully!", "success")

        return redirect(url_for("admin.dashboard"))

    return render_template(
        "edit_project.html",
        project=project,
        technologies=technologies,
        assigned_technologies=assigned_technologies
    )

@admin.route('/admin/delete-project/<int:project_id>', methods=["POST"])
def delete_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT image FROM projects WHERE id = %s",
        (project_id,)
    )

    project = cursor.fetchone()

    if project is None:
        cursor.close()
        abort(404)

    cursor.close()

    if project["image"]:
        image_path = os.path.join(
            "static/images/projects",
            project["image"]
        )

        if os.path.exists(image_path):
            os.remove(image_path)

    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM projects WHERE id = %s",
        (project_id,)
    )

    db.commit()
    cursor.close()

    flash("Project deleted successfully!", "success")
    return redirect(url_for("admin.dashboard"))


@admin.route('/admin/add-skill', methods = ["GET", "POST"])
def add_skill():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        proficiency = request.form["proficiency"]
        cursor = db.cursor()

        cursor.execute("INSERT INTO skills (name, category, proficiency) VALUES (%s, %s, %s)", (name, category, proficiency))
        db.commit()
        cursor.close()
        flash("Skill added successfully!", "success")
        return redirect(url_for('admin.dashboard'))
    return render_template("add_skill.html")

@admin.route('/admin/edit-skill/<int:skill_id>', methods = ["GET", "POST"])
def edit_skill(skill_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM skills WHERE id = %s", (skill_id,))

    skill = cursor.fetchone()

    cursor.close()

    if skill is None:
        abort(404)

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        proficiency = request.form["proficiency"]

        cursor = db.cursor()


        cursor.execute("UPDATE skills SET name = %s, category = %s, proficiency = %s WHERE id = %s", (name, category, proficiency, skill_id))

        db.commit()
        cursor.close()
        flash("Skill updated successfully!", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("edit_skill.html", skill = skill)

@admin.route('/admin/delete-skill/<int:skill_id>', methods = ["POST"])
def delete_skill(skill_id):
    if "user_id" not in session:
        return redirect(url_for('auth.login'))


    cursor = db.cursor()

    cursor.execute("DELETE FROM skills WHERE id = %s", (skill_id,))

    db.commit()
    cursor.close()
    flash("Skill deleted successfully!", "success")
    return redirect(url_for('admin.dashboard'))

@admin.route("/admin/messages")
def messages():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM messages
        ORDER BY created_at DESC
    """)

    messages = cursor.fetchall()

    cursor.close()

    return render_template("messages.html", messages=messages)

@admin.route('/admin/delete-messages/<int:message_id>', methods = ["POST"])
def delete_message(message_id):
    if "user_id" not in session:
        return redirect(url_for('auth.login'))

    cursor = db.cursor()

    cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))

    db.commit()
    cursor.close()


    flash("Message deleted successfully!", "success")

    return redirect(url_for('admin.messages'))

