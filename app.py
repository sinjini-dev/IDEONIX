from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, json, requests
from datetime import datetime

GEMINI_API_KEY = "AIzaSyDPZYcwKOw8BGmaRmx9H9ULRvL0m25-0a4"

def ask_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    res = requests.post(url, json=body)
    data = res.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

app = Flask(__name__)
app.secret_key = "ideonix_secret_2024"

DB = "ideonix.db"

# ─── Database Setup ───────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,          -- 'ngo' or 'volunteer'
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ngo_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            org_name TEXT NOT NULL,
            location TEXT,
            description TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS volunteer_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            skills TEXT,           -- comma-separated
            availability TEXT,     -- e.g. "weekends", "weekdays", "anytime"
            location TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ngo_user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            location TEXT,
            required_skills TEXT,
            urgency TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ngo_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            volunteer_user_id INTEGER NOT NULL,
            ai_reason TEXT,
            score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id),
            FOREIGN KEY(volunteer_user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ─── Helpers ──────────────────────────────────────────────────────────────────

def current_user():
    return session.get("user_id")

def get_user(uid):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user

# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        name     = request.form["name"].strip()
        email    = request.form["email"].strip().lower()
        password = request.form["password"]
        role     = request.form["role"]          # ngo or volunteer

        # Extra profile fields
        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            flash("Email already registered.", "error")
            conn.close()
            return redirect(url_for("signup"))

        hashed = generate_password_hash(password)
        c = conn.cursor()
        c.execute("INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
                  (name, email, hashed, role))
        uid = c.lastrowid

        if role == "ngo":
            org_name    = request.form.get("org_name", name)
            location    = request.form.get("location", "")
            description = request.form.get("description", "")
            c.execute("INSERT INTO ngo_profiles (user_id,org_name,location,description) VALUES (?,?,?,?)",
                      (uid, org_name, location, description))
        else:
            skills       = request.form.get("skills", "")
            availability = request.form.get("availability", "anytime")
            location     = request.form.get("location", "")
            c.execute("INSERT INTO volunteer_profiles (user_id,skills,availability,location) VALUES (?,?,?,?)",
                      (uid, skills, availability, location))

        conn.commit()
        conn.close()
        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["role"]    = user["role"]
            session["name"]    = user["name"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    if not current_user():
        return redirect(url_for("login"))
    role = session["role"]
    conn = get_db()

    if role == "ngo":
        tasks = conn.execute(
            "SELECT * FROM tasks WHERE ngo_user_id=? ORDER BY created_at DESC",
            (current_user(),)
        ).fetchall()
        profile = conn.execute("SELECT * FROM ngo_profiles WHERE user_id=?", (current_user(),)).fetchone()
        conn.close()
        return render_template("dashboard_ngo.html", tasks=tasks, profile=profile)
    else:
        profile = conn.execute("SELECT * FROM volunteer_profiles WHERE user_id=?", (current_user(),)).fetchone()
        matches = conn.execute("""
            SELECT m.*, t.title, t.description, t.location, t.urgency, t.required_skills,
                   u.name as ngo_name
            FROM matches m
            JOIN tasks t ON m.task_id = t.id
            JOIN users u ON t.ngo_user_id = u.id
            WHERE m.volunteer_user_id=?
            ORDER BY m.created_at DESC
        """, (current_user(),)).fetchall()
        conn.close()
        return render_template("dashboard_volunteer.html", profile=profile, matches=matches)

# ─── Tasks (NGO) ──────────────────────────────────────────────────────────────

@app.route("/tasks/new", methods=["GET","POST"])
def new_task():
    if not current_user() or session["role"] != "ngo":
        return redirect(url_for("login"))
    if request.method == "POST":
        title    = request.form["title"]
        desc     = request.form["description"]
        location = request.form["location"]
        skills   = request.form["required_skills"]
        urgency  = request.form["urgency"]
        conn = get_db()
        conn.execute(
            "INSERT INTO tasks (ngo_user_id,title,description,location,required_skills,urgency) VALUES (?,?,?,?,?,?)",
            (current_user(), title, desc, location, skills, urgency)
        )
        conn.commit()
        conn.close()
        flash("Task posted successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template("new_task.html")

@app.route("/tasks")
def all_tasks():
    conn = get_db()
    tasks = conn.execute("""
        SELECT t.*, u.name as ngo_name, n.org_name
        FROM tasks t
        JOIN users u ON t.ngo_user_id = u.id
        JOIN ngo_profiles n ON t.ngo_user_id = n.user_id
        WHERE t.status='open'
        ORDER BY CASE t.urgency WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, t.created_at DESC
    """).fetchall()
    conn.close()
    return render_template("tasks.html", tasks=tasks)

# ─── AI Matching ──────────────────────────────────────────────────────────────

@app.route("/match/<int:task_id>", methods=["POST"])
def run_match(task_id):
    """NGO triggers AI matching for a specific task."""
    if not current_user() or session["role"] != "ngo":
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    volunteers = conn.execute("""
        SELECT u.id, u.name, vp.skills, vp.availability, vp.location
        FROM users u JOIN volunteer_profiles vp ON u.id = vp.user_id
        WHERE u.role='volunteer'
    """).fetchall()

    if not volunteers:
        conn.close()
        return jsonify({"error": "No volunteers registered yet."}), 400

    # Build prompt
    vol_list = "\n".join([
        f"- ID:{v['id']} | {v['name']} | Skills: {v['skills']} | Availability: {v['availability']} | Location: {v['location']}"
        for v in volunteers
    ])
    prompt = f"""You are an AI volunteer coordinator for IDEONIX, a social impact platform.

TASK:
Title: {task['title']}
Description: {task['description']}
Location: {task['location']}
Required Skills: {task['required_skills']}
Urgency: {task['urgency']}

AVAILABLE VOLUNTEERS:
{vol_list}

Analyze each volunteer and return a JSON array of matches ranked by suitability.
Each object must have: volunteer_id (integer), score (0-100), reason (1-2 sentences).
Return ONLY valid JSON, no markdown fences.
Example: [{{"volunteer_id":1,"score":92,"reason":"..."}}]"""

    try:
        raw = ask_gemini(prompt).strip()
        raw = raw.replace("json","").replace("","").strip()
        matches_data = json.loads(raw)

        # Save matches to DB
        conn.execute("DELETE FROM matches WHERE task_id=?", (task_id,))
        for m in matches_data:
            conn.execute(
                "INSERT INTO matches (task_id,volunteer_user_id,ai_reason,score) VALUES (?,?,?,?)",
                (task_id, m["volunteer_id"], m["reason"], m["score"])
            )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "matches": matches_data})

    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/match/global", methods=["POST"])
def global_match():
    """Run AI matching for ALL open tasks at once."""
    if not current_user() or session["role"] != "ngo":
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    tasks = conn.execute("SELECT * FROM tasks WHERE ngo_user_id=? AND status='open'", (current_user(),)).fetchall()
    volunteers = conn.execute("""
        SELECT u.id, u.name, vp.skills, vp.availability, vp.location
        FROM users u JOIN volunteer_profiles vp ON u.id = vp.user_id
        WHERE u.role='volunteer'
    """).fetchall()
    conn.close()

    if not tasks or not volunteers:
        return jsonify({"error": "Need at least one task and one volunteer."}), 400

    task_list = "\n".join([
        f"- TaskID:{t['id']} | {t['title']} | Skills: {t['required_skills']} | Urgency: {t['urgency']}"
        for t in tasks
    ])
    vol_list = "\n".join([
        f"- VolID:{v['id']} | {v['name']} | Skills: {v['skills']} | Avail: {v['availability']}"
        for v in volunteers
    ])

    prompt = f"""You are IDEONIX's AI coordinator. Match volunteers to NGO tasks.

TASKS:
{task_list}

VOLUNTEERS:
{vol_list}

Return a JSON array. Each item: task_id, volunteer_id, score (0-100), reason.
Return ONLY valid JSON array, no markdown."""

    try:
        raw = ask_gemini(prompt).strip()
        raw = raw.replace("json","").replace("","").strip()
        matches_data = json.loads(raw)

        conn = get_db()
        for m in matches_data:
            conn.execute("DELETE FROM matches WHERE task_id=? AND volunteer_user_id=?",
                         (m["task_id"], m["volunteer_id"]))
            conn.execute(
                "INSERT INTO matches (task_id,volunteer_user_id,ai_reason,score) VALUES (?,?,?,?)",
                (m["task_id"], m["volunteer_id"], m["reason"], m["score"])
            )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "matches": matches_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/match/status/<int:task_id>")
def match_status(task_id):
    conn = get_db()
    results = conn.execute("""
        SELECT m.score, m.ai_reason, m.status, u.name, vp.skills, vp.availability, vp.location
        FROM matches m
        JOIN users u ON m.volunteer_user_id = u.id
        JOIN volunteer_profiles vp ON u.id = vp.user_id
        WHERE m.task_id=?
        ORDER BY m.score DESC
    """, (task_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in results])

@app.route("/match/accept/<int:match_id>", methods=["POST"])
def accept_match(match_id):
    if not current_user() or session["role"] != "volunteer":
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    conn.execute("UPDATE matches SET status='accepted' WHERE id=? AND volunteer_user_id=?",
                 (match_id, current_user()))
    conn.commit()
    conn.close()
    flash("You accepted the task!", "success")
    return redirect(url_for("dashboard"))

# ─── Analytics ────────────────────────────────────────────────────────────────

@app.route("/analytics")
def analytics():
    if not current_user():
        return redirect(url_for("login"))
    conn = get_db()
    stats = {
        "total_volunteers": conn.execute("SELECT COUNT(*) FROM users WHERE role='volunteer'").fetchone()[0],
        "total_ngos":       conn.execute("SELECT COUNT(*) FROM users WHERE role='ngo'").fetchone()[0],
        "total_tasks":      conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
        "open_tasks":       conn.execute("SELECT COUNT(*) FROM tasks WHERE status='open'").fetchone()[0],
        "total_matches":    conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0],
        "accepted_matches": conn.execute("SELECT COUNT(*) FROM matches WHERE status='accepted'").fetchone()[0],
    }
    urgency_data = conn.execute(
        "SELECT urgency, COUNT(*) as cnt FROM tasks GROUP BY urgency"
    ).fetchall()
    conn.close()
    return render_template("analytics.html", stats=stats, urgency_data=urgency_data)

if __name__ == "_main_":
    app.run(debug=True, port=5000)