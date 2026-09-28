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

    cursor.execute("""
        SELECT
            projects.id,
            projects.title,
            projects.description,
            GROUP_CONCAT(DISTINCT technologies.name SEPARATOR ', ') AS technologies
        FROM projects

        LEFT JOIN project_technologies
            ON projects.id = project_technologies.project_id

        LEFT JOIN technologies
            ON project_technologies.technology_id = technologies.id

        WHERE projects.title LIKE %s
           OR projects.description LIKE %s
           OR technologies.name LIKE %s

        GROUP BY
            projects.id,
            projects.title,
            projects.description

    """, (
        f"%{query}%",
        f"%{query}%",
        f"%{query}%"
    ))

    projects = cursor.fetchall()

    cursor.close()

    return render_template(
        "search.html",
        projects=projects,
        query=query
    )

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

    cursor.execute("""
        SELECT
            projects.id,
            projects.title,
            projects.description,
            GROUP_CONCAT(technologies.name SEPARATOR', ') AS technologies
            FROM projects
            LEFT JOIN project_technologies
                ON projects.id = project_technologies.project_id
            LEFT JOIN technologies
                ON project_technologies.technology_id = technologies.id
        
            GROUP BY projects.id
        """)
    projects = cursor.fetchall()

    cursor.execute("SELECT * FROM skills")
    skills = cursor.fetchall()

    cursor.execute("SELECT * FROM messages ORDER BY created_at DESC")
    messages = cursor.fetchall()

    cursor.close()


    return render_template("admin.html", projects = projects, skills = skills, messages = messages)


@app.route("/admin/messages")
def messages():
    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM messages
        ORDER BY created_at DESC
    """)

    messages = cursor.fetchall()

    cursor.close()

    return render_template("messages.html", messages=messages)

@app.route('/admin/delete-messages<int:message_id>', methods = ["POST"])
def delete_message(message_id):
    if "user_id" not in session:
        return redirect(url_for('login'))

    cursor = db.cursor()

    cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))

    db.commit()
    cursor.close()


    flash("Message deleted successfully!", "success")

    return redirect(url_for('messages'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route('/admin/add-project', methods = ["GET", "POST"])
def add_project():
    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM technologies ORDER BY name")

    technologies = cursor.fetchall()
    cursor.close()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        technology_ids = request.form.getlist("technologies")

        cursor = db.cursor()

        cursor.execute("INSERT INTO projects (title, description) VALUES (%s, %s)", (title,
        description))

        project_id = cursor.lastrowid

        for technology_id in technology_ids:
            cursor.execute("""
                INSERT INTO project_technologies (project_id, technology_id)
                VALUES(%s, %s)
                """,
                (project_id, technology_id)
                )
        db.commit()
        cursor.close()

        flash("Project added successfully!", "success")

        return redirect(url_for("admin"))
    return render_template("add_project.html",
                           technologies = technologies)

@app.route('/admin/edit-project/<int:project_id>', methods = ["GET", "POST"])
def edit_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()

    cursor.execute("SELECT * FROM technologies ORDER BY name")
    technologies = cursor.fetchall()

    cursor.execute("""
        SELECT technology_id
        FROM project_technologies
        WHERE project_id = %s""",
        (project_id,))

    assigned_technologies = cursor.fetchall()
    cursor.close()

    if project is None:
        abort(404)

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        technology_ids = request.form.getlist("technologies")

        cursor = db.cursor()

        cursor.execute("""UPDATE projects
                       SET title = %s,
                       description = %s
                       WHERE id = %s""",
                       (title, description, project_id))

        cursor.execute("DELETE FROM project_technologies WHERE project_id = %s", 
                       (project_id,))
        for technology_id in technology_ids:
            cursor.execute("""
                    INSERT INTO project_technologies(project_id, technology_id)
                    VALUES(%s, %s)
                    """,
                    (project_id, technology_id)
                    )
        db.commit()
        cursor.close()
        flash("Project updated successfully!", "success")
        return redirect(url_for("admin"))

    return render_template("edit_project.html", 
                           project = project,
                           technologies = technologies,
                           assigned_technologies = assigned_technologies
                           )

    
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

    cursor.execute("""
        SELECT
            projects.id,
            projects.title,
            projects.description,
            GROUP_CONCAT(technologies.name SEPARATOR ', ') AS technologies
            FROM projects
            LEFT JOIN project_technologies
                ON projects.id = project_technologies.project_id
            LEFT JOIN technologies
                ON project_technologies.technology_id = technologies.id
            GROUP BY projects.id
        """)
    projects = cursor.fetchall()


    cursor.close()
    return render_template("projects.html", projects = projects)

@app.route('/projects/<int:project_id>')
def project_detail(project_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))

    project = cursor.fetchone();

    cursor.execute("""
        SELECT technologies.name
        FROM project_technologies
        JOIN technologies
            ON project_technologies.technology_id = technologies.id
        WHERE project_technologies.project_id = %s
    """, (project_id,))

    technologies = cursor.fetchall()

    cursor.close()
    if project is None:
        abort(404)

    return render_template("project.html", project = project, technologies = technologies)   

@app.route('/contact', methods = ["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        cursor = db.cursor()
        cursor.execute("INSERT INTO messages (name, email, message) VALUES (%s, %s, %s)", (name, email, message))
        db.commit()
        cursor.close()

        flash("Message sent successfully!", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


if __name__ == '__main__':
    app.run(debug=True)  