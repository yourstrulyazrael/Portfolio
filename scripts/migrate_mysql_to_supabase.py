"""One-off copy of the local MySQL database (and uploaded files) into Supabase.

Run from the project root after running supabase/schema.sql in the Supabase SQL Editor:

    .venv\\Scripts\\python.exe scripts\\migrate_mysql_to_supabase.py

Reads the old DB_HOST / DB_USER / DB_PASSWORD / DB_NAME and the new SUPABASE_* values from .env.
Rows keep their original ids so links between tables stay intact. It refuses to run if any
Supabase table already has rows, so it can't create duplicates.
"""
import mimetypes
import os
import sys
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from dotenv import load_dotenv

from database import supabase, bucket
from routes.common import PROJECT_IMAGE_FOLDER, CERTIFICATE_FOLDER

load_dotenv()

# Parents before children, so foreign keys always point at rows that already exist
TABLES = [
    "users", "skills", "technologies", "projects",
    "project_technologies", "project_images", "certificates", "messages",
]

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "images")


def to_json(value):
    if isinstance(value, datetime):
        # MySQL TIMESTAMP values come back naive in local time
        return value.astimezone().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def upload_local_file(folder, filename):
    path = os.path.join(STATIC_DIR, folder, filename)
    if not os.path.exists(path):
        print(f"  ! missing local file {folder}/{filename}, skipped")
        return
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(path, "rb") as file:
        bucket().upload(f"{folder}/{filename}", file.read(), {"content-type": content_type, "upsert": "true"})
    print(f"  uploaded {folder}/{filename}")


def main():
    for table in TABLES:
        if supabase.table(table).select("*", count="exact", head=True).execute().count:
            sys.exit(f"Supabase table '{table}' already has rows. Empty it first; nothing was copied.")

    source = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )
    cursor = source.cursor(dictionary=True)

    copied = {}
    for table in TABLES:
        cursor.execute(f"SELECT * FROM {table}")
        rows = [{column: to_json(value) for column, value in row.items()} for row in cursor.fetchall()]
        if rows:
            supabase.table(table).insert(rows).execute()
        copied[table] = rows
        print(f"{table}: {len(rows)} row(s)")

    cursor.close()
    source.close()

    # New rows must not reuse the ids we just copied
    supabase.rpc("sync_id_sequences").execute()

    print("files:")
    for image in copied["project_images"]:
        upload_local_file(PROJECT_IMAGE_FOLDER, image["filename"])
    for certificate in copied["certificates"]:
        if certificate["file"]:
            upload_local_file(CERTIFICATE_FOLDER, certificate["file"])

    print("Done.")


if __name__ == "__main__":
    main()
