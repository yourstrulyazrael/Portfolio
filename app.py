from routes.public import public
from routes.auth import auth
from routes.admin import admin
from routes.common import media_url, get_site_settings, get_profile, ACCENTS, PROJECT_STATUSES
from flask import Flask, render_template, flash, redirect, request
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect, CSRFError
from config import SECRET_KEY
from database import supabase
from routes.auth import get_user, password_problems
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import click
from functools import lru_cache
import hashlib
import os


app = Flask(__name__, static_folder="public", static_url_path="")
app.register_blueprint(public)
app.register_blueprint(auth)
app.register_blueprint(admin)
app.secret_key = SECRET_KEY
if not SECRET_KEY:
    app.logger.error(
        "SECRET_KEY is not set, so the login and contact pages cannot work. Add it to .env locally and to "
        "Vercel -> Settings -> Environment Variables (then redeploy). Generate one with: "
        "python -c \"import secrets; print(secrets.token_hex(32))\""
    )
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("VERCEL") == "1"
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
csrf = CSRFProtect(app)


@lru_cache(maxsize=None)
def asset_version(path):
    file_path = os.path.join(app.static_folder, path)
    with open(file_path, "rb") as file:
        return hashlib.md5(file.read()).hexdigest()[:10]


def asset_url(path):
    version = asset_version(path) if not app.debug else str(int(os.path.getmtime(os.path.join(app.static_folder, path))))
    return f"/{path}?v={version}"


@app.context_processor
def inject_globals():
    return {
        "current_year": datetime.now().year,
        "media_url": media_url,
        "asset_url": asset_url,
        "site_settings": get_site_settings(),
        "theme_accents": ACCENTS,
        "profile": get_profile(),
        "project_statuses": PROJECT_STATUSES,
    }


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(413)
def file_too_large(error):
    flash("Upload is too large. The total size must be under 32 MB.", "danger")
    return redirect(request.url)


@app.cli.command("set-admin-password", help="Create the admin account or reset its password (also clears any login lockout).")
@click.option("--username", prompt="Admin username", default="admin", show_default=True)
@click.password_option(prompt="New password")
def set_admin_password(username, password):
    problems = password_problems(password, username)
    if problems:
        raise click.ClickException(" ".join(problems))

    fields = {"username": username, "password": generate_password_hash(password)}
    user = get_user(username=username)
    if user:
        supabase.table("users").update(fields).eq("id", user["id"]).execute()
    else:
        supabase.table("users").insert(fields).execute()
    try:
        supabase.table("users").update({"failed_logins": 0, "locked_until": None}).eq("username", username).execute()
    except Exception:
        pass
    click.echo(f"Password {'updated' if user else 'set'} for '{username}'. Other signed-in sessions are signed out.")


@app.errorhandler(CSRFError)
def csrf_failed(error):
    flash("Your session expired or the form was out of date. Please try again.", "danger")
    return redirect(request.url)


@app.errorhandler(500)
def internal_server_error(error):
    return render_template("500.html"), 500


if __name__ == '__main__':
    app.run(debug=True)  