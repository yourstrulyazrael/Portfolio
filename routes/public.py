from flask import Blueprint, render_template, abort, request, flash, redirect, url_for
from database import db

public = Blueprint('public', __name__)

@public.route('/')
def home():
    return render_template("index.html")

@public.route('/projects')
def project_page():
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


    cursor.close()
    return render_template("projects.html", projects = projects)

@public.route('/skills')
def skills_page():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM skills")
    skills = cursor.fetchall()
    cursor.close()
    return render_template("skills.html", skills = skills)

@public.route('/projects/<int:project_id>')
def project_detail(project_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))

    project = cursor.fetchone();

    cursor.execute("""
        SELECT technologies.name
        FROM project_technologies
        JOIN technologies
            ON project_technologies.technology_id = technologies.id
        WHERE project_technologies.project_id = %s
    """, (project_id,))

    technologies = cursor.fetchall()

    cursor.close()
    if project is None:
        abort(404)

    return render_template("project.html", project = project, technologies = technologies)

@public.route('/contact', methods = ["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        cursor = db.cursor()
        cursor.execute("INSERT INTO messages (name, email, message) VALUES (%s, %s, %s)", (name, email, message))
        db.commit()
        cursor.close()

        flash("Message sent successfully!", "success")
        return redirect(url_for("public.contact"))

    return render_template("contact.html")

@public.route("/search") 
def search():

    query = request.args.get("q", "")

    cursor = db.cursor(dictionary=True) 

    cursor.execute("""
        SELECT
            projects.id,
            projects.title,
            projects.description,
            GROUP_CONCAT(DISTINCT technologies.name SEPARATOR ', ') AS technologies
        FROM projects

        LEFT JOIN project_technologies
            ON projects.id = project_technologies.project_id

        LEFT JOIN technologies
            ON project_technologies.technology_id = technologies.id

        WHERE projects.title LIKE %s
           OR projects.description LIKE %s
           OR technologies.name LIKE %s

        GROUP BY
            projects.id,
            projects.title,
            projects.description

    """, (
        f"%{query}%",
        f"%{query}%",
        f"%{query}%"
    ))

    projects = cursor.fetchall()

    cursor.close()

    return render_template(
        "search.html",
        projects=projects,
        query=query
    )