from flask import Blueprint, render_template, abort, request, flash, redirect, url_for
from database import supabase
from routes.common import list_projects, get_project, list_certificates, list_skills_by_category

public = Blueprint('public', __name__)

@public.route('/')
def home():
    featured_projects = list_projects(limit=2, newest_first=True)
    skill_groups = list_skills_by_category()
    return render_template("index.html", featured_projects = featured_projects, skill_groups = skill_groups)

@public.route('/projects')
def project_page():
    projects = list_projects()
    return render_template("projects.html", projects = projects)

@public.route('/skills')
def skills_page():
    skill_groups = list_skills_by_category()
    return render_template("skills.html", skill_groups = skill_groups)

@public.route('/projects/<int:project_id>')
def project_detail(project_id):
    project = get_project(project_id)

    if project is None:
        abort(404)

    return render_template("project.html", project = project, technologies = project["technology_list"], images = project["images"])

@public.route('/certificates')
def certificates_page():
    certificates = list_certificates()
    return render_template("certificates.html", certificates = certificates)

@public.route('/contact', methods = ["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        supabase.table("messages").insert({"name": name, "email": email, "message": message}).execute()

        flash("Message sent successfully!", "success")
        return redirect(url_for("public.contact"))

    return render_template("contact.html")

@public.route("/search")
def search():

    query = request.args.get("q", "").strip()
    needle = query.lower()

    # A portfolio has few projects, so match in Python rather than building a
    # PostgREST OR filter across the embedded technologies from user input.
    projects = [
        project for project in list_projects()
        if needle in project["title"].lower()
        or needle in project["description"].lower()
        or any(needle in technology["name"].lower() for technology in project["technology_list"])
    ]

    return render_template(
        "search.html",
        projects=projects,
        query=query
    )
