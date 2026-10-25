from flask import Blueprint, render_template, abort, request, flash, redirect, url_for, jsonify, Response
from database import supabase, bucket
from routes.common import (list_projects, get_project, list_certificates, list_skills_by_category,
                           project_matches, featured_projects, list_testimonials, get_profile,
                           PROJECT_SORTS, PROFILE_FOLDER)

public = Blueprint('public', __name__)

@public.route('/')
def home():
    projects = list_projects(newest_first=True)
    skill_groups = list_skills_by_category()
    certificates = list_certificates()
    stats = {
        "projects": len(projects),
        "skills": sum(len(skills) for _, skills in skill_groups),
        "certificates": len(certificates),
    }
    return render_template(
        "index.html",
        featured_projects = featured_projects(projects),
        testimonials = list_testimonials(),
        skill_groups = skill_groups,
        latest_certificates = certificates[:3],
        stats = stats,
        skill_names = [skill["name"] for _, skills in skill_groups for skill in skills],
    )

@public.route('/projects')
def project_page():
    query = request.args.get("q", "").strip()[:100]
    selected = sorted({name.strip().lower() for name in request.args.getlist("tech") if name.strip()})
    sort = request.args.get("sort", "featured")
    if sort not in PROJECT_SORTS:
        sort = "featured"

    projects = sorted(list_projects(), key=PROJECT_SORTS[sort][1])

    technologies = {}
    for project in projects:
        for technology in project["technology_list"]:
            key = technology["name"].lower()
            technologies[key] = (technology["name"], technologies.get(key, ("", 0))[1] + 1)

    matches = {project["id"] for project in projects if project_matches(project, query, selected)}

    return render_template(
        "projects.html",
        projects=projects,
        matches=matches,
        query=query,
        selected=selected,
        sort=sort,
        sorts=PROJECT_SORTS,
        technologies=sorted(technologies.items(), key=lambda item: item[1][0].lower()),
    )

@public.route('/skills')
def skills_page():
    skills = supabase.table("skills").select("*").order("id").execute().data
    return render_template("skills.html", skills = skills)

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
    return redirect(url_for("public.project_page", q=request.args.get("q", "").strip() or None))


@public.route("/about")
def about():
    skill_groups = list_skills_by_category()
    return render_template(
        "about.html",
        skill_groups=skill_groups,
        testimonials=list_testimonials(),
        project_count=len(list_projects()),
    )


@public.route("/cv")
def cv():
    cv_file = get_profile()["cv_file"]
    if not cv_file:
        abort(404)
    options = {"download": "James-Israel-Figueroa-CV.pdf"} if request.args.get("download") else None
    return redirect(bucket().get_public_url(f"{PROFILE_FOLDER}/{cv_file}", options))


SITE_PAGES = [
    ("public.home", "Home", "README.md"),
    ("public.about", "About", "about.md"),
    ("public.project_page", "Projects", "projects/"),
    ("public.skills_page", "Skills", "skills.json"),
    ("public.certificates_page", "Certificates", "certificates.yml"),
    ("public.contact", "Contact", "contact.sh"),
]


@public.route("/sitemap.xml")
def sitemap():
    urls = [url_for(endpoint, _external=True) for endpoint, _, _ in SITE_PAGES]
    urls += [url_for("public.project_detail", project_id=project["id"], _external=True) for project in list_projects()]
    xml = render_template("sitemap.xml", urls=urls)
    return Response(xml, mimetype="application/xml")


@public.route("/robots.txt")
def robots():
    lines = [
        "User-agent: *",
        "Disallow: /admin",
        "Disallow: /login",
        "Disallow: /api/",
        f"Sitemap: {url_for('public.sitemap', _external=True)}",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@public.route("/api/site.json")
def site_index():
    profile = get_profile()
    skill_groups = list_skills_by_category()
    response = jsonify(
        pages=[{"title": title, "file": file, "url": url_for(endpoint)} for endpoint, title, file in SITE_PAGES],
        projects=[
            {
                "id": project["id"],
                "title": project["title"],
                "description": project["description"],
                "technologies": [technology["name"] for technology in project["technology_list"]],
                "status": project["status"],
                "url": url_for("public.project_detail", project_id=project["id"]),
                "live_url": project["live_url"],
                "github_url": project["github_url"],
            }
            for project in sorted(list_projects(), key=PROJECT_SORTS["featured"][1])
        ],
        skills={category: [skill["name"] for skill in skills] for category, skills in skill_groups},
        profile={
            "name": profile["full_name"],
            "headline": profile["headline"],
            "location": profile["location"],
            "email": profile["email"],
            "availability": profile["availability"],
            "links": {label.lower(): url for label, url, _ in profile["social_links"]},
            "cv": url_for("public.cv") if profile["cv_file"] else None,
        },
    )
    response.headers["Cache-Control"] = "public, max-age=60"
    return response
