import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')

SUPABASE_URL = os.getenv('SUPABASE_URL')
# Server-side only: the secret / service_role key bypasses Row Level Security.
SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY')
SUPABASE_BUCKET = os.getenv('SUPABASE_BUCKET', 'portfolio')
