from flask import g
from database import supabase, bucket, first, parse_date, parse_datetime

THEMES = ("system", "dark", "light")
ACCENTS = ("emerald", "violet", "blue", "cyan", "amber", "rose", "orange", "pink", "lime", "indigo", "mono")
DEFAULT_SETTINGS = {"theme": "system", "accent": "emerald"}


def get_site_settings():

    if "site_settings" not in g:
        try:
            row = first(supabase.table("site_settings").select("theme, accent").eq("id", 1).limit(1).execute())
        except Exception:
            row = None
        settings = dict(DEFAULT_SETTINGS)
        if row:
            if row.get("theme") in THEMES:
                settings["theme"] = row["theme"]
            if row.get("accent") in ACCENTS:
                settings["accent"] = row["accent"]
        g.site_settings = settings
    return g.site_settings

PROJECT_IMAGE_FOLDER = "projects"
CERTIFICATE_FOLDER = "certificates"
PROFILE_FOLDER = "profile"

DEFAULT_PROFILE = {
    "full_name": "James Israel Figueroa",
    "headline": "BSIT student & aspiring web developer",
    "bio": (
        "I'm an aspiring IT professional building my skills in software development, "
        "web development, databases, and cybersecurity. This portfolio showcases the "
        "projects I've built and the technologies I'm currently learning."
    ),
    "location": None,
    "email": None,
    "availability": None,
    "github_url": None,
    "linkedin_url": None,
    "website_url": None,
    "cv_file": None,
}
PROFILE_FIELDS = tuple(DEFAULT_PROFILE)
BLANK_LINE = "\n\n"
LIST_MARKERS = " -*\t"


def get_profile():
    if "profile" not in g:
        try:
            row = first(supabase.table("profile").select("*").eq("id", 1).limit(1).execute()) or {}
        except Exception:
            row = {}
        profile = {field: row.get(field) or default for field, default in DEFAULT_PROFILE.items()}
        profile["bio_paragraphs"] = [part.strip() for part in profile["bio"].replace("\r", "").split(BLANK_LINE) if part.strip()]
        profile["social_links"] = [
            (label, url, glyph) for label, url, glyph in [
                ("GitHub", profile["github_url"], "github"),
                ("LinkedIn", profile["linkedin_url"], "linkedin"),
                ("Website", profile["website_url"], "globe"),
            ] if url
        ]
        g.profile = profile
    return g.profile

PROJECT_SELECT = "*, technologies(id, name), project_images(id, filename, sort_order)"


def media_url(folder, filename):
    return bucket().get_public_url(f"{folder}/{filename}")


def shape_project(row):
    images = sorted(row.pop("project_images", []), key=lambda image: (image["sort_order"], image["id"]))
    technologies = sorted(row.pop("technologies", []), key=lambda technology: technology["name"].lower())

    row["images"] = images
    row["image_count"] = len(images)
    row["cover_image"] = images[0]["filename"] if images else None
    row["technology_list"] = technologies
    row["technologies"] = ", ".join(technology["name"] for technology in technologies) or None
    row["demo_credentials"] = row.get("demo_credentials") or []
    row["status"] = row.get("status") if row.get("status") in PROJECT_STATUSES else "completed"
    row["featured"] = bool(row.get("featured"))
    row["sort_order"] = row.get("sort_order") or 0
    row["feature_list"] = [line.strip(LIST_MARKERS) for line in (row.get("features") or "").splitlines() if line.strip(LIST_MARKERS)]
    row["started_on"] = parse_date(row.get("started_on"))
    row["finished_on"] = parse_date(row.get("finished_on"))
    for field in ("role", "problem", "solution", "challenges"):
        row[field] = row.get(field) or None
    row["search_text"] = " ".join(
        [row["title"], row.get("description") or ""] + [technology["name"] for technology in technologies]
    ).lower()
    return row


def list_projects(limit=None, newest_first=False):
    query = supabase.table("projects").select(PROJECT_SELECT).order("id", desc=newest_first)
    if limit:
        query = query.limit(limit)
    return [shape_project(row) for row in query.execute().data]


PROJECT_STATUSES = {"completed": "Completed", "in_progress": "In progress", "archived": "Archived"}


def featured_key(project):
    return (not project["featured"], project["sort_order"], -project["id"])


PROJECT_SORTS = {
    "featured": ("Featured", featured_key),
    "newest": ("Newest first", lambda project: -project["id"]),
    "oldest": ("Oldest first", lambda project: project["id"]),
    "name": ("Name (A-Z)", lambda project: project["title"].lower()),
}


def project_matches(project, query="", technologies=()):
    names = {technology["name"].lower() for technology in project["technology_list"]}
    return (all(word in project["search_text"] for word in query.lower().split())
            and set(technologies) <= names)


def featured_projects(projects, limit=3):
    chosen = [project for project in projects if project["featured"]] or projects
    return sorted(chosen, key=featured_key)[:limit]


def list_testimonials():
    try:
        return supabase.table("testimonials").select("*").order("sort_order").order("id").execute().data
    except Exception:
        return []


def list_skills_by_category():
    skills = supabase.table("skills").select("*").order("category").order("name").execute().data
    groups = {}
    for skill in skills:
        groups.setdefault(skill["category"], []).append(skill)
    return list(groups.items())


def get_project(project_id):
    rows = supabase.table("projects").select(PROJECT_SELECT).eq("id", project_id).execute().data
    return shape_project(rows[0]) if rows else None


def shape_certificate(row):
    row["issue_date"] = parse_date(row.get("issue_date"))
    return row


def list_certificates():
    rows = (
        supabase.table("certificates").select("*")
        .order("issue_date", desc=True, nullsfirst=False)
        .order("id", desc=True)
        .execute().data
    )
    return [shape_certificate(row) for row in rows]


def list_messages():
    rows = supabase.table("messages").select("*").order("created_at", desc=True).execute().data
    for row in rows:
        row["created_at"] = parse_datetime(row["created_at"])
    return rows
