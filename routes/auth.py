from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import db
from werkzeug.security import check_password_hash

auth = Blueprint('auth', __name__)

@auth.route('/login', methods = ["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))

        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect(url_for("admin.dashboard"))
        flash("Invalid username or password", "error")
        return redirect(url_for("auth.login"))
    return render_template("login.html")

@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("auth.login"))