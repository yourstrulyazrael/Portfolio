from datetime import date, datetime

from supabase import create_client
from config import SUPABASE_URL, SUPABASE_SECRET_KEY, SUPABASE_BUCKET

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SECRET_KEY must be set: in .env locally, or in the "
        "host's environment variables when deployed (e.g. Vercel -> Settings -> "
        "Environment Variables). Values are in Supabase -> Project Settings -> API Keys."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def bucket():
    return supabase.storage.from_(SUPABASE_BUCKET)


def first(response):
    """The first row of a query response, or None when nothing matched."""
    return response.data[0] if response.data else None


def parse_date(value):
    """Supabase returns dates as ISO strings; templates expect date objects."""
    return date.fromisoformat(value) if value else None


def parse_datetime(value):
    """Parse a timestamptz string and convert it from UTC to the server's local time."""
    return datetime.fromisoformat(value).astimezone() if value else None
