import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).resolve().parent / "instance" / "studenthub.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT UNIQUE,
                password TEXT NOT NULL DEFAULT 'student123',
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                gender TEXT,
                course_id INTEGER NOT NULL,
                date_of_birth TEXT,
                enrollment_date TEXT DEFAULT (DATE('now')),
                status TEXT NOT NULL DEFAULT 'Active',
                address TEXT DEFAULT '',
                blood_group TEXT DEFAULT 'O+',
                FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Present',
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
                UNIQUE (student_id, date)
            );
        """)

        # Migration: ensure username and password columns exist in students table
        cols = [c[1] for c in conn.execute("PRAGMA table_info(students)").fetchall()]
        if "username" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN username TEXT")
        if "password" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN password TEXT NOT NULL DEFAULT 'student123'")

        # Ensure all existing students have clean usernames and passwords
        existing = conn.execute("SELECT id, name, email, username, password FROM students").fetchall()
        for s in existing:
            first = s["name"].split()[0].lower()
            uname = s["username"]
            if not uname or uname.strip() == "":
                # Check for username collision
                taken = conn.execute("SELECT COUNT(*) FROM students WHERE username = ? AND id != ?", (first, s["id"])).fetchone()[0]
                uname = first if taken == 0 else f"{first}{s['id']}"
                pwd = f"{uname}123"
                conn.execute("UPDATE students SET username = ?, password = ? WHERE id = ?", (uname, pwd, s["id"]))
            elif not s["password"] or s["password"].strip() == "":
                conn.execute("UPDATE students SET password = ? WHERE id = ?", (f"{uname}123", s["id"]))

        # Seed courses if table is fresh
        if conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
            courses = [
                ("BCA", "BCA-101"),
                ("BSc IT", "IT-201"),
                ("MCA", "MCA-301"),
                ("BTech Computer Science", "CS-401"),
                ("BBA", "BBA-102"),
                ("MCom", "MCOM-202")
            ]
            conn.executemany("INSERT INTO courses (name, code) VALUES (?, ?)", courses)

        # Seed initial batch of students if empty
        if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            students = [
                ("Aarav Sharma", "aarav", "aarav123", "aarav.sharma@example.in", "+91 98201 12233", "Male", 1, "2003-04-12", "2025-06-15", "Active", "14 Connaught Place, New Delhi", "O+"),
                ("Ananya Iyer", "ananya", "ananya123", "ananya.iyer@example.in", "+91 98402 23344", "Female", 4, "2003-08-21", "2025-06-18", "Active", "28 T. Nagar, Chennai", "A+"),
                ("Rohan Verma", "rohan", "rohan123", "rohan.verma@example.in", "+91 98113 34455", "Male", 2, "2002-11-10", "2025-06-20", "Active", "56 Hazratganj, Lucknow", "B+"),
                ("Priya Patel", "priya", "priya123", "priya.patel@example.in", "+91 98984 45566", "Female", 5, "2003-03-17", "2025-07-01", "Active", "89 CG Road, Ahmedabad", "O+"),
                ("Siddharth Deshmukh", "siddharth", "siddharth123", "siddharth.d@example.in", "+91 98225 56677", "Male", 3, "2001-05-14", "2025-06-22", "Active", "102 FC Road, Shivaji Nagar, Pune", "AB+"),
                ("Kavya Reddy", "kavya", "kavya123", "kavya.reddy@example.in", "+91 98496 67788", "Female", 4, "2002-01-25", "2025-06-25", "Active", "44 Banjara Hills, Hyderabad", "B+"),
                ("Vikram Joshi", "vikram", "vikram123", "vikram.joshi@example.in", "+91 98277 78899", "Male", 1, "2002-09-09", "2025-07-03", "Inactive", "31 MI Road, Jaipur", "A-"),
                ("Sneha Nair", "sneha", "sneha123", "sneha.nair@example.in", "+91 98478 89900", "Female", 6, "2001-12-04", "2025-07-05", "Active", "19 Panampilly Nagar, Kochi", "O+"),
                ("Aditya Kulkarni", "aditya", "aditya123", "aditya.k@example.in", "+91 98239 90011", "Male", 2, "2002-06-19", "2025-06-28", "Active", "77 Marine Drive, Churchgate, Mumbai", "B+"),
                ("Tanvi Gupta", "tanvi", "tanvi123", "tanvi.gupta@example.in", "+91 98100 01122", "Female", 5, "2003-09-29", "2025-07-08", "Inactive", "65 Sector 17, Chandigarh", "AB-"),
                ("Ishaan Chawla", "ishaan", "ishaan123", "ishaan.c@example.in", "+91 98765 00112", "Male", 1, "2003-05-15", "2025-07-10", "Active", "22 Golf Links, New Delhi", "B+"),
                ("Pooja Hegde", "pooja", "pooja123", "pooja.h@example.in", "+91 98401 11223", "Female", 1, "2003-09-12", "2025-07-12", "Active", "12 Anna Salai, Chennai", "O+"),
                ("Vedant Patel", "vd", "ved", "ved@gmail.com", "+91 98200 99887", "Male", 5, "2002-04-18", "2025-07-15", "Active", "42 Juhu Tara Road, Mumbai", "B+"),
                ("Meera Krishnamurthy", "meera", "meera123", "meera.k@example.in", "+91 98312 11234", "Female", 1, "2003-07-14", "2025-08-01", "Active", "5 Indira Nagar, Bangalore", "A+"),
                ("Arjun Malhotra", "arjun", "arjun123", "arjun.m@example.in", "+91 98765 22345", "Male", 4, "2002-02-28", "2025-08-03", "Active", "78 Sector 22, Noida", "O+"),
                ("Ritika Bose", "ritika", "ritika123", "ritika.b@example.in", "+91 98651 33456", "Female", 2, "2003-11-05", "2025-08-05", "Active", "33 Lake Town, Kolkata", "B-"),
                ("Karan Mehrotra", "karan", "karan123", "karan.meh@example.in", "+91 98204 44567", "Male", 3, "2001-08-18", "2025-08-07", "Active", "91 Civil Lines, Allahabad", "AB+"),
                ("Divya Subramaniam", "divya", "divya123", "divya.s@example.in", "+91 98507 55678", "Female", 6, "2002-05-23", "2025-08-09", "Active", "17 Anna Nagar, Coimbatore", "O+"),
                ("Rahul Tripathi", "rahult", "rahult123", "rahul.t@example.in", "+91 98302 66789", "Male", 1, "2003-01-30", "2025-08-11", "Active", "42 Hazaribagh Road, Ranchi", "B+"),
                ("Pooja Menon", "poojaM", "poojaM123", "pooja.menon@example.in", "+91 98423 77890", "Female", 5, "2002-09-12", "2025-08-13", "Inactive", "8 Palarivattom, Kochi", "A-"),
                ("Sameer Qureshi", "sameer", "sameer123", "sameer.q@example.in", "+91 98556 88901", "Male", 2, "2001-12-07", "2025-08-15", "Active", "55 Mominpura, Nagpur", "O-"),
                ("Nandini Agarwal", "nandini", "nandini123", "nandini.a@example.in", "+91 98765 99012", "Female", 4, "2003-03-25", "2025-08-17", "Active", "19 Gomti Nagar, Lucknow", "AB-"),
                ("Vishal Pandey", "vishal", "vishal123", "vishal.p@example.in", "+91 98201 00123", "Male", 1, "2002-06-09", "2025-08-19", "Active", "67 Patna City, Patna", "B+"),
                ("Shreya Jain", "shreya", "shreya123", "shreya.j@example.in", "+91 98344 11234", "Female", 3, "2003-10-14", "2025-08-21", "Active", "23 Sarojini Nagar, New Delhi", "O+"),
                ("Harshit Sharma", "harshit", "harshit123", "harshit.s@example.in", "+91 98657 22345", "Male", 6, "2001-04-04", "2025-08-23", "Active", "88 Andheri West, Mumbai", "A+")
            ]
            conn.executemany("""
                INSERT INTO students 
                (name, username, password, email, phone, gender, course_id, date_of_birth, enrollment_date, status, address, blood_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, students)

        # Seed recent attendance logs
        if conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0] == 0:
            student_rows = conn.execute("SELECT id, status FROM students").fetchall()
            today = datetime.now()
            recent_dates = []
            cur_date = today
            while len(recent_dates) < 5:
                if cur_date.weekday() < 5:
                    recent_dates.append(cur_date.strftime("%Y-%m-%d"))
                cur_date -= timedelta(days=1)

            att_records = []
            for s in student_rows:
                for idx, dt in enumerate(recent_dates):
                    if s["status"] == "Active":
                        att_status = "Present" if (s["id"] + idx) % 5 != 0 else "Late"
                    else:
                        att_status = "Absent"
                    att_records.append((s["id"], dt, att_status))

            conn.executemany("""
                INSERT OR IGNORE INTO attendance (student_id, date, status)
                VALUES (?, ?, ?)
            """, att_records)


def get_student_attendance(student_id):
    with get_db() as conn:
        row = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent,
                SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late
            FROM attendance
            WHERE student_id = ?
        """, (student_id,)).fetchone()

    total = row["total"] or 0
    attended = row["attended"] or 0
    pct = round((attended / total) * 100) if total > 0 else 90

    return {
        "total": total,
        "attended": attended,
        "absent": row["absent"] or 0,
        "late": row["late"] or 0,
        "percentage": pct
    }


# Backwards compatibility helpers
get_db_connection = get_db
get_engine_name = lambda: "SQLite"
get_student_attendance_stats = lambda sid: {
    "total_days": get_student_attendance(sid)["total"],
    "attended_days": get_student_attendance(sid)["attended"],
    "absent_days": get_student_attendance(sid)["absent"],
    "late_days": get_student_attendance(sid)["late"],
    "percentage": get_student_attendance(sid)["percentage"]
}

if __name__ == "__main__":
    init_db()
    print("Database checked and ready at", DB_PATH)
