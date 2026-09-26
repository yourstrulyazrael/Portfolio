from flask import Flask, render_template, flash, url_for, redirect, request, abort, session
from werkzeug.security import check_password_hash
import mysql.connector

app = Flask(__name__)
app.secret_key = "1234"
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="portfolio_db"
)

print("Database connected")


@app.route('/')
def home():
    return render_template("index.html")

@app.route("/search") 
def search(): 
    query = request.args.get("q", "") 
    cursor = db.cursor(dictionary=True) 
    cursor.execute(""" SELECT * FROM projects WHERE title LIKE %s OR description LIKE %s OR technology LIKE %s """, ( f"%{query}%", f"%{query}%", f"%{query}%" )) 
    projects = cursor.fetchall() 
    cursor.close() 
    return render_template("search.html", projects=projects, query=query)

@app.route('/login', methods = ["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("admin"))
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

            return redirect(url_for("admin"))
        flash("Invalid username or password", "error")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route('/admin')
def admin():
    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM projects")
    projects = cursor.fetchall()

    cursor.execute("SELECT * FROM skills")
    skills = cursor.fetchall()

    cursor.close()


    return render_template("admin.html", projects = projects, skills = skills)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route('/admin/add-project', methods = ["GET", "POST"])
def add_project():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        technology = request.form["technology"]

        cursor = db.cursor()

        cursor.execute("INSERT INTO projects (title, description, technology) VALUES (%s, %s, %s)", (title,
        description, technology))
        db.commit()
        cursor.close()

        flash("Project added successfully!", "success")

        return redirect(url_for("admin"))
    return render_template("add_project.html")

@app.route('/admin/edit-project/<int:project_id>', methods = ["GET", "POST"])
def edit_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))

    project = cursor.fetchone()
    cursor.close()

    if project is None:
        abort(404)

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        technology = request.form["technology"]

        cursor = db.cursor()

        cursor.execute("""UPDATE projects
                       SET title = %s,
                       description = %s,
                       technology = %s
                       WHERE id = %s""", 
                       (title, description, technology, project_id))
        db.commit()
        cursor.close()
        flash("Project updated successfully!", "success")
        return redirect(url_for("admin"))

    return render_template("edit_project.html", project = project)

    
@app.route('/admin/delete-project/<int:project_id>', methods = ["POST"])
def delete_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    cursor = db.cursor()

    cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    
    db.commit()
    cursor.close()

    flash("Project deleted successfully!", "success")

    return redirect(url_for("admin"))
    



@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/skills')
def skills_page():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM skills")
    skills = cursor.fetchall()
    cursor.close()
    return render_template("skills.html", skills = skills)

@app.route('/admin/add-skill', methods = ["GET", "POST"])
def add_skill():
    if "user_id" not in session:
        return redirect("login")

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        proficiency = request.form["proficiency"]
        cursor = db.cursor()

        cursor.execute("INSERT INTO skills (name, category, proficiency) VALUES (%s, %s, %s)", (name, category, proficiency))
        db.commit()
        cursor.close()
        flash("Skill added successfully!", "success")
        return redirect(url_for('admin'))
    return render_template("add_skill.html")

@app.route('/admin/edit-skill/<int:skill_id>', methods = ["GET", "POST"])
def edit_skill(skill_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM skills WHERE id = %s", (skill_id,))

    skill = cursor.fetchone()

    cursor.close()

    if skill is None:
        abort(404)

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        proficiency = request.form["proficiency"]

        cursor = db.cursor()


        cursor.execute("UPDATE skills SET name = %s, category = %s, proficiency = %s WHERE id = %s", (name, category, proficiency, skill_id))

        db.commit()
        cursor.close()
        flash("Skill updated successfully!", "success")
        return redirect(url_for("admin"))
    return render_template("edit_skill.html", skill = skill)

@app.route('/admin/delete-skill/<int:skill_id>', methods = ["POST"])
def delete_skill(skill_id):
    if "user_id" not in session:
        return redirect(url_for('login'))


    cursor = db.cursor()

    cursor.execute("DELETE FROM skills WHERE id = %s", (skill_id,))

    db.commit()
    cursor.close()
    flash("Skill deleted successfully!", "success")
    return redirect(url_for('admin'))

@app.route('/projects')
def project_page():
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM projects")
    projects = cursor.fetchall()
    cursor.close()
    return render_template("projects.html", projects = projects)

@app.route('/projects/<int:project_id>')
def project_detail(project_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))

    project = cursor.fetchone();

    cursor.close()
    if project is None:
        abort(404)

    return render_template("project.html", project = project)   

@app.route('/contact')
def contact():
    return render_template("contact.html")


if __name__ == '__main__':
    app.run(debug=True)  