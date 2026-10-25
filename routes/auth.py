from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import supabase, first
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta, timezone
import hashlib
import re

auth = Blueprint('auth', __name__)

MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)
MIN_PASSWORD_LENGTH = 12
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")
COMMON_PASSWORDS = {
    "admin", "administrator", "password", "passw0rd", "123456", "12345678", "123456789", "1234567890",
    "qwerty", "qwertyuiop", "letmein", "welcome", "iloveyou", "changeme", "portfolio", "admin123",
    "admin1234", "password1", "password123", "qwerty123", "abc123", "111111", "000000",
}
DUMMY_HASH = generate_password_hash("timing-equaliser-not-a-real-password")


def password_problems(password, username=""):
    problems = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > 128:
        problems.append("Use at most 128 characters.")
    if password.lower() in COMMON_PASSWORDS or len(set(password)) < 4:
        problems.append("That password is too common or too simple.")
    if username and len(username) >= 3 and username.lower() in password.lower():
        problems.append("Don't include your username in the password.")
    return problems


def password_fingerprint(password_hash):
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def get_user(**match):
    query = supabase.table("users").select("*")
    for column, value in match.items():
        query = query.eq(column, value)
    return first(query.limit(1).execute())


def record_login_failure(user):
    failures = (user.get("failed_logins") or 0) + 1
    fields = {"failed_logins": failures}
    if failures >= MAX_FAILED_LOGINS:
        fields = {"failed_logins": 0, "locked_until": (datetime.now(timezone.utc) + LOCKOUT).isoformat()}
    try:
        supabase.table("users").update(fields).eq("id", user["id"]).execute()
    except Exception:
        pass
    return failures >= MAX_FAILED_LOGINS


def locked_minutes(user):
    locked_until = user.get("locked_until")
    if not locked_until:
        return 0
    remaining = datetime.fromisoformat(locked_until) - datetime.now(timezone.utc)
    return max(0, int(remaining.total_seconds() // 60) + 1) if remaining.total_seconds() > 0 else 0


def start_session(user, must_change_password=False):
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["pw"] = password_fingerprint(user["password"])
    if must_change_password:
        session["must_change_password"] = True


@auth.route('/login', methods = ["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()[:50]
        password = request.form.get("password", "")[:128]

        user = get_user(username=username) if username else None

        if user and locked_minutes(user):
            minutes = locked_minutes(user)
            flash(f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.", "danger")
            return redirect(url_for("auth.login"))

        if user is None:
            check_password_hash(DUMMY_HASH, password)
        elif check_password_hash(user["password"], password):
            if user.get("failed_logins") or user.get("locked_until"):
                try:
                    supabase.table("users").update({"failed_logins": 0, "locked_until": None}).eq("id", user["id"]).execute()
                except Exception:
                    pass
            weak = bool(password_problems(password, user["username"]))
            start_session(user, must_change_password=weak)
            if weak:
                flash("Your password is too weak. Choose a new one to continue.", "warning")
                return redirect(url_for("admin.account"))
            return redirect(url_for("admin.dashboard"))
        elif record_login_failure(user):
            flash(f"Too many failed attempts. Try again in {int(LOCKOUT.total_seconds() // 60)} minutes.", "danger")
            return redirect(url_for("auth.login"))

        flash("Invalid username or password", "danger")
        return redirect(url_for("auth.login"))
    return render_template("login.html")


@auth.route('/logout', methods=["POST"])
def logout():
    session.clear()
    flash("You've been signed out.", "success")
    return redirect(url_for("auth.login"))
