import csv
import io
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    Response
)
from database import get_db, init_db, get_student_attendance, get_engine_name, get_student_attendance_stats

app = Flask(__name__)
app.secret_key = "studenthub-portal-secret-key"

# Ensure database is prepared
init_db()


@app.context_processor
def global_context():
    return {
        "db_engine": "SQLite",
        "current_year": datetime.now().year
    }


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # 1. Administrator credentials
        if identifier == "admin" and password == "admin123":
            session.clear()
            session["user"] = "admin"
            session["role"] = "Administrator"
            session["logged_in"] = True
            flash("Signed in successfully as Administrator.", "success")
            return redirect(url_for("dashboard"))

        # 2. Student credentials from database (matches username, email, or full name)
        with get_db() as db:
            student = db.execute("""
                SELECT s.*, c.name as course
                FROM students s
                JOIN courses c ON s.course_id = c.id
                WHERE (LOWER(s.username) = LOWER(?) OR LOWER(s.email) = LOWER(?) OR LOWER(s.name) = LOWER(?))
                  AND s.password = ?
            """, (identifier, identifier, identifier, password)).fetchone()

        if student:
            session.clear()
            session["user"] = student["name"]
            session["username"] = student["username"]
            session["student_id"] = student["id"]
            session["role"] = "Student"
            session["logged_in"] = True
            flash(f"Welcome back, {student['name']}!", "success")
            return redirect(url_for("student_detail", student_id=student["id"]))

        flash("Invalid username/email or password.", "error")

    return render_template("login.html", active_page="login")


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("dashboard"))


# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------

@app.route("/")
def dashboard():
    with get_db() as db:
        stats = {
            "total_students": db.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "active_students": db.execute("SELECT COUNT(*) FROM students WHERE status = 'Active'").fetchone()[0],
            "inactive_students": db.execute("SELECT COUNT(*) FROM students WHERE status = 'Inactive'").fetchone()[0],
            "male_students": db.execute("SELECT COUNT(*) FROM students WHERE gender = 'Male'").fetchone()[0],
            "female_students": db.execute("SELECT COUNT(*) FROM students WHERE gender = 'Female'").fetchone()[0],
            "total_courses": db.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
        }

        recent_students = db.execute("""
            SELECT s.id, s.name, s.email, s.status, c.name as course
            FROM students s
            JOIN courses c ON s.course_id = c.id
            ORDER BY s.id DESC
            LIMIT 5
        """).fetchall()

        course_stats = db.execute("""
            SELECT c.name as course, COUNT(s.id) as total
            FROM courses c
            LEFT JOIN students s ON c.id = s.course_id
            GROUP BY c.id
            HAVING total > 0
            ORDER BY total DESC
        """).fetchall()

        chart_labels = [c["course"] for c in course_stats]
        chart_data = [c["total"] for c in course_stats]

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        recent_students=recent_students,
        course_stats=course_stats,
        chart_labels=chart_labels,
        chart_data=chart_data,
        **stats
    )


# -----------------------------------------------------------------------------
# Student Directory & CRUD
# -----------------------------------------------------------------------------

@app.route("/students")
def students():
    query = request.args.get("search", "").strip()
    course_id = request.args.get("course_id", "").strip()
    status = request.args.get("status", "").strip()

    sql = """
        SELECT s.id, s.name, s.username, s.password, s.email, s.phone, s.gender, s.status, s.blood_group, c.name as course
        FROM students s
        JOIN courses c ON s.course_id = c.id
        WHERE 1 = 1
    """
    params = []

    if query:
        sql += " AND (s.name LIKE ? OR s.username LIKE ? OR s.email LIKE ? OR s.phone LIKE ? OR c.name LIKE ?)"
        wildcard = f"%{query}%"
        params.extend([wildcard, wildcard, wildcard, wildcard, wildcard])

    if course_id:
        sql += " AND s.course_id = ?"
        params.append(course_id)

    if status:
        sql += " AND s.status = ?"
        params.append(status)

    sql += " ORDER BY s.id DESC"

    with get_db() as db:
        student_list = db.execute(sql, params).fetchall()
        courses = db.execute("SELECT id, name FROM courses ORDER BY name").fetchall()
        active_count = db.execute("SELECT COUNT(*) FROM students WHERE status = 'Active'").fetchone()[0]
        inactive_count = db.execute("SELECT COUNT(*) FROM students WHERE status = 'Inactive'").fetchone()[0]

    return render_template(
        "students.html",
        active_page="students",
        students=student_list,
        courses=courses,
        search=query,
        selected_course=course_id,
        selected_status=status,
        active_count=active_count,
        inactive_count=inactive_count
    )


@app.route("/student/add", methods=["GET", "POST"])
@app.route("/add", methods=["GET", "POST"])
def add_student():
    if session.get("role") != "Administrator":
        flash("Administrator authorization required to enroll new students.", "error")
        return redirect(url_for("students"))

    with get_db() as db:
        courses = db.execute("SELECT id, name FROM courses ORDER BY name").fetchall()

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            gender = request.form.get("gender", "").strip()
            course_id = request.form.get("course_id", "").strip()
            dob = request.form.get("date_of_birth", "").strip() or None
            status = request.form.get("status", "Active").strip()
            blood_group = request.form.get("blood_group", "O+").strip()
            address = request.form.get("address", "").strip()

            if not name or not email or not course_id:
                flash("Name, email, and course are mandatory.", "error")
                return render_template("student_form.html", student=request.form, courses=courses, form_title="Add Student")

            if not username:
                username = name.split()[0].lower()
                taken = db.execute("SELECT COUNT(*) FROM students WHERE username = ?", (username,)).fetchone()[0]
                if taken > 0:
                    username = f"{username}{int(datetime.now().timestamp()) % 1000}"
            if not password:
                password = f"{username}123"

            try:
                cur = db.execute("""
                    INSERT INTO students (name, username, password, email, phone, gender, course_id, date_of_birth, status, address, blood_group)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, username, password, email, phone, gender, course_id, dob, status, address, blood_group))
                new_id = cur.lastrowid
                flash(f"Enrolled {name} successfully (Username: {username}).", "success")
                return redirect(url_for("student_detail", student_id=new_id))
            except Exception as e:
                flash(f"Could not save student: {e}", "error")

    return render_template("student_form.html", student=None, courses=courses, form_title="Add Student", active_page="add_student")


@app.route("/student/<int:student_id>")
@app.route("/students/<int:student_id>")
def student_detail(student_id):
    with get_db() as db:
        student = db.execute("""
            SELECT s.*, c.name as course
            FROM students s
            JOIN courses c ON s.course_id = c.id
            WHERE s.id = ?
        """, (student_id,)).fetchone()

    if not student:
        flash("Student profile not found.", "error")
        return redirect(url_for("students"))

    attendance_stats = get_student_attendance_stats(student_id)

    return render_template("student_detail.html", student=student, attendance_stats=attendance_stats, active_page="students")


@app.route("/student/edit/<int:student_id>", methods=["GET", "POST"])
@app.route("/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    is_admin = session.get("role") == "Administrator"
    is_self = session.get("student_id") == student_id

    # Only admin can edit other profiles; students can only edit their own
    if not (is_admin or is_self):
        flash("You only have permission to edit your own profile.", "error")
        return redirect(url_for("student_detail", student_id=student_id))

    with get_db() as db:
        student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        courses = db.execute("SELECT id, name FROM courses ORDER BY name").fetchall()

        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("students"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip() or student["username"] or name.split()[0].lower()
            password = request.form.get("password", "").strip() or student["password"] or "student123"
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            gender = request.form.get("gender", "").strip()
            dob = request.form.get("date_of_birth", "").strip() or None
            blood_group = request.form.get("blood_group", "O+").strip()
            address = request.form.get("address", "").strip()

            # Course and Status are restricted to administrators
            if is_admin:
                course_id = request.form.get("course_id", "").strip() or student["course_id"]
                status = request.form.get("status", "Active").strip()
            else:
                course_id = student["course_id"]
                status = student["status"]

            try:
                db.execute("""
                    UPDATE students
                    SET name=?, username=?, password=?, email=?, phone=?, gender=?, course_id=?, date_of_birth=?, status=?, address=?, blood_group=?
                    WHERE id=?
                """, (name, username, password, email, phone, gender, course_id, dob, status, address, blood_group, student_id))

                # Keep session in sync if editing own profile
                if is_self:
                    session["user"] = name
                    session["username"] = username

                flash("Profile updated successfully.", "success")
                return redirect(url_for("student_detail", student_id=student_id))
            except Exception as e:
                flash(f"Update failed: {e}", "error")

    return render_template(
        "student_form.html",
        student=student,
        courses=courses,
        form_title="Edit My Profile" if is_self and not is_admin else "Edit Student",
        active_page="students"
    )


@app.route("/student/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    # Only administrators can delete profiles
    if session.get("role") != "Administrator":
        flash("Administrator authorization required to delete student profiles.", "error")
        return redirect(url_for("students"))

    with get_db() as db:
        db.execute("DELETE FROM students WHERE id = ?", (student_id,))
    flash("Record removed.", "success")
    return redirect(url_for("students"))


@app.route("/student/toggle-status/<int:student_id>", methods=["POST"])
def toggle_status(student_id):
    # Only administrators can change enrollment status
    if session.get("role") != "Administrator":
        flash("Administrator authorization required to change enrollment status.", "error")
        return redirect(request.referrer or url_for("students"))

    with get_db() as db:
        row = db.execute("SELECT status, name FROM students WHERE id = ?", (student_id,)).fetchone()
        if row:
            next_status = "Inactive" if row["status"] == "Active" else "Active"
            db.execute("UPDATE students SET status = ? WHERE id = ?", (next_status, student_id))
            flash(f"Marked {row['name']} as {next_status}.", "success")

    return redirect(request.referrer or url_for("students"))


# -----------------------------------------------------------------------------
# Attendance
# -----------------------------------------------------------------------------

@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    with get_db() as db:
        if request.method == "POST":
            # Only administrators can save attendance records
            if session.get("role") != "Administrator":
                flash("Administrator sign-in required to edit attendance records.", "error")
                return redirect(url_for("attendance"))

            att_date = request.form.get("date", datetime.now().strftime("%Y-%m-%d"))
            course_id = request.form.get("course_id", "")
            student_rows = db.execute("SELECT id FROM students").fetchall()

            for s in student_rows:
                key = f"att_{s['id']}"
                if key in request.form:
                    val = request.form[key]
                    db.execute("DELETE FROM attendance WHERE student_id = ? AND date = ?", (s["id"], att_date))
                    db.execute("INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)", (s["id"], att_date, val))

            flash(f"Attendance saved for {att_date}.", "success")
            return redirect(url_for("attendance", date=att_date, course_id=course_id))

        selected_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
        selected_course = request.args.get("course_id", "")

        sql = """
            SELECT s.id, s.name, s.email, s.status, c.name as course
            FROM students s
            JOIN courses c ON s.course_id = c.id
        """
        params = []
        if selected_course:
            sql += " WHERE s.course_id = ?"
            params.append(selected_course)

        sql += " ORDER BY s.name ASC"
        student_list = db.execute(sql, params).fetchall()

        logs = db.execute("SELECT student_id, status FROM attendance WHERE date = ?", (selected_date,)).fetchall()
        attendance_map = {row["student_id"]: row["status"] for row in logs}

        present_count = sum(1 for s in student_list if attendance_map.get(s["id"]) == "Present")
        absent_count = sum(1 for s in student_list if attendance_map.get(s["id"]) == "Absent")
        late_count = sum(1 for s in student_list if attendance_map.get(s["id"]) == "Late")
        courses = db.execute("SELECT id, name FROM courses ORDER BY name").fetchall()

    return render_template(
        "attendance.html",
        active_page="attendance",
        students=student_list,
        courses=courses,
        selected_date=selected_date,
        selected_course=selected_course,
        attendance_map=attendance_map,
        present_count=present_count,
        absent_count=absent_count,
        late_count=late_count
    )


# -----------------------------------------------------------------------------
# Courses
# -----------------------------------------------------------------------------

@app.route("/courses")
def courses_page():
    with get_db() as db:
        courses = db.execute("""
            SELECT c.id, c.name, c.code, COUNT(s.id) as enrolled_count
            FROM courses c
            LEFT JOIN students s ON c.id = s.course_id
            GROUP BY c.id
            ORDER BY c.name ASC
        """).fetchall()

    return render_template("courses.html", courses=courses, active_page="courses")


@app.route("/courses/add", methods=["POST"])
def add_course():
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip()

    if name:
        with get_db() as db:
            try:
                db.execute("INSERT INTO courses (name, code) VALUES (?, ?)", (name, code))
                flash(f"Course '{name}' added.", "success")
            except Exception as e:
                flash(f"Could not add course: {e}", "error")
    else:
        flash("Course name cannot be blank.", "error")

    return redirect(url_for("courses_page"))


@app.route("/courses/delete/<int:course_id>", methods=["POST"])
def delete_course(course_id):
    with get_db() as db:
        count = db.execute("SELECT COUNT(*) FROM students WHERE course_id = ?", (course_id,)).fetchone()[0]
        if count > 0:
            flash("Cannot remove course with enrolled students.", "error")
        else:
            db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
            flash("Course deleted.", "success")

    return redirect(url_for("courses_page"))


# -----------------------------------------------------------------------------
# CSV Export & JSON APIs
# -----------------------------------------------------------------------------

@app.route("/students/export")
def export_csv():
    with get_db() as db:
        rows = db.execute("""
            SELECT s.id, s.name, s.username, s.password, s.email, s.phone, s.gender, c.name as course, 
                   s.date_of_birth, s.enrollment_date, s.status, s.blood_group, s.address
            FROM students s
            JOIN courses c ON s.course_id = c.id
            ORDER BY s.id ASC
        """).fetchall()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["ID", "Name", "Username", "Password", "Email", "Phone", "Gender", "Course", "Date of Birth", "Enrollment Date", "Status", "Blood Group", "Address"])
    for r in rows:
        writer.writerow([r["id"], r["name"], r["username"], r["password"], r["email"], r["phone"], r["gender"], r["course"], r["date_of_birth"], r["enrollment_date"], r["status"], r["blood_group"], r["address"]])

    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=students.csv"})


@app.route("/api/students")
def api_students():
    q = request.args.get("search", "").strip()
    with get_db() as db:
        if q:
            term = f"%{q}%"
            rows = db.execute("""
                SELECT s.id, s.name, s.username, s.email, s.phone, s.gender, c.name as course, s.status
                FROM students s
                JOIN courses c ON s.course_id = c.id
                WHERE s.name LIKE ? OR s.username LIKE ? OR s.email LIKE ? OR s.phone LIKE ? OR c.name LIKE ?
                ORDER BY s.id DESC
            """, (term, term, term, term, term)).fetchall()
        else:
            rows = db.execute("""
                SELECT s.id, s.name, s.username, s.email, s.phone, s.gender, c.name as course, s.status
                FROM students s
                JOIN courses c ON s.course_id = c.id
                ORDER BY s.id DESC
            """).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/api/students/active")
def api_active_students():
    with get_db() as db:
        rows = db.execute("""
            SELECT s.id, s.name, s.email, s.phone, s.gender, c.name as course, s.status
            FROM students s
            JOIN courses c ON s.course_id = c.id
            WHERE s.status = 'Active'
            ORDER BY s.name ASC
        """).fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    app.run(debug=True)
