from database import supabase, bucket, parse_date, parse_datetime

# Folders inside the Supabase Storage bucket
PROJECT_IMAGE_FOLDER = "projects"
CERTIFICATE_FOLDER = "certificates"

# PostgREST embeds technologies through the project_technologies junction table
PROJECT_SELECT = "id, title, description, github_url, technologies(id, name), project_images(id, filename, sort_order)"


def media_url(folder, filename):
    """Public URL of a file in the Storage bucket."""
    return bucket().get_public_url(f"{folder}/{filename}")


def shape_project(row):
    """Flatten an embedded project row into the fields the templates use."""
    images = sorted(row.pop("project_images", []), key=lambda image: (image["sort_order"], image["id"]))
    technologies = sorted(row.pop("technologies", []), key=lambda technology: technology["name"].lower())

    row["images"] = images
    row["image_count"] = len(images)
    row["cover_image"] = images[0]["filename"] if images else None
    row["technology_list"] = technologies
    row["technologies"] = ", ".join(technology["name"] for technology in technologies) or None
    return row


def list_projects():
    rows = supabase.table("projects").select(PROJECT_SELECT).order("id").execute().data
    return [shape_project(row) for row in rows]


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
