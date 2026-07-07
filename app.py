import os
import json
import sqlite3
from datetime import date, timedelta
from flask import Flask, request, jsonify, session, g, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import requests

load_dotenv()  # reads variables from a local .env file

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-this-before-deploy")

DATABASE = os.path.join(os.path.dirname(__file__), "career_copilot.db")
PATTERNS_FILE = os.path.join(os.path.dirname(__file__), "data", "company_patterns.json")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"


# ---------- DB HELPERS ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
            db.executescript(f.read())
        db.commit()
    print("Database initialized.")


def current_user():
    """Returns the logged-in user's row, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Login required"}), 401
        return view(*args, **kwargs)

    return wrapped


# ---------- AUTH ROUTES ----------

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are all required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        return jsonify({"error": "An account with this email already exists."}), 409

    password_hash = generate_password_hash(password)
    cursor = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    db.execute(
        "INSERT INTO streaks (user_id, current_streak, longest_streak) VALUES (?, 0, 0)",
        (cursor.lastrowid,),
    )
    db.commit()

    session["user_id"] = cursor.lastrowid
    session["user_name"] = name
    return jsonify({"message": "Account created.", "name": name}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return jsonify({"message": "Logged in.", "name": user["name"]}), 200


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out."}), 200


@app.route("/api/me", methods=["GET"])
def me():
    user = current_user()
    if not user:
        return jsonify({"logged_in": False}), 200
    return jsonify({"logged_in": True, "name": user["name"], "email": user["email"]}), 200


# ---------- READINESS ANALYZER ----------

def load_company_patterns():
    with open(PATTERNS_FILE, "r") as f:
        return json.load(f)


@app.route("/api/analyze", methods=["POST"])
@login_required
def analyze():
    data = request.get_json(force=True)
    target_name = (data.get("target_name") or "").strip()
    resume_text = (data.get("resume_text") or "").strip()
    target_type = (data.get("target_type") or "internship").strip()  # internship / hackathon / placement

    if not target_name or not resume_text:
        return jsonify({"error": "Target name and resume/GitHub text are both required."}), 400

    patterns = load_company_patterns()
    has_curated_data = target_name in patterns
    data_source = "curated" if has_curated_data else "general_knowledge"

    system_prompt = (
        "You are a career-readiness analyst helping a beginner CS student in India "
        "prepare for a specific internship, hackathon, or placement target. "
        "Compare the student's profile against realistic expectations for this target, honestly. "
        "Respond with ONLY valid JSON, no markdown formatting, no preamble, "
        "in exactly this shape: "
        '{"strengths": ["..."], "gaps": ["..."], "prioritized_fix_list": ["..."], '
        '"overall_readiness_score": 0}. '
        "overall_readiness_score is an integer 0-100. Be honest, not falsely encouraging — "
        "a beginner benefits more from accurate gaps than empty praise."
    )

    if has_curated_data:
        company_data = patterns[target_name]
        user_prompt = (
            f"Target ({target_type}): {target_name}\n\n"
            f"Real interview pattern data for this target:\n{json.dumps(company_data, indent=2)}\n\n"
            f"Student's resume/GitHub summary:\n{resume_text}\n\n"
            "Compare the student's current profile against the real pattern data above. "
            "Return the JSON object described in the system prompt."
        )
    else:
        user_prompt = (
            f"Target ({target_type}): {target_name}\n\n"
            "We don't have curated real interview data for this specific target yet, so use your "
            "general knowledge of what this kind of internship, hackathon, or placement process "
            "typically looks like (rounds, common topics/judging criteria, difficulty level).\n\n"
            f"Student's resume/GitHub summary:\n{resume_text}\n\n"
            "Compare the student's current profile against realistic expectations for this target. "
            "Return the JSON object described in the system prompt."
        )

    try:
        gemini_payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
        }
        gemini_response = requests.post(GEMINI_URL, json=gemini_payload, timeout=30)
        gemini_response.raise_for_status()
        raw_text = gemini_response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Strip accidental markdown code fences if the model adds them
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        return jsonify({"error": "AI response wasn't valid JSON. Try again."}), 502
    except Exception as e:
        return jsonify({"error": f"AI request failed: {str(e)}"}), 502

    # Save each gap to the database so the Tracker can reference it later
    db = get_db()
    user_id = session["user_id"]
    gap_ids = []
    for gap_desc in result.get("gaps", []):
        cursor = db.execute(
            "INSERT INTO gaps (user_id, target_name, gap_description, priority, status) "
            "VALUES (?, ?, ?, 'medium', 'open')",
            (user_id, target_name, gap_desc),
        )
        gap_ids.append(cursor.lastrowid)

    db.execute(
        "INSERT INTO readiness_scores (user_id, target_name, score, recap_notes) VALUES (?, ?, ?, ?)",
        (user_id, target_name, result.get("overall_readiness_score", 0), "Initial analysis"),
    )
    db.commit()

    result["gap_ids"] = gap_ids
    result["data_source"] = data_source
    return jsonify(result), 200


# ---------- DAILY TRACKER ----------

@app.route("/api/gaps", methods=["GET"])
@login_required
def get_gaps():
    db = get_db()
    user_id = session["user_id"]
    rows = db.execute(
        "SELECT id, target_name, gap_description, status FROM gaps "
        "WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return jsonify([dict(row) for row in rows]), 200


@app.route("/api/log", methods=["POST"])
@login_required
def log_activity():
    data = request.get_json(force=True)
    activity = (data.get("activity") or "").strip()
    gap_id = data.get("gap_id")  # optional, may be None
    minutes_spent = data.get("minutes_spent")

    if not activity:
        return jsonify({"error": "Please describe what you practiced today."}), 400

    db = get_db()
    user_id = session["user_id"]
    today = date.today().isoformat()

    db.execute(
        "INSERT INTO daily_logs (user_id, gap_id, log_date, activity, minutes_spent) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, gap_id, today, activity, minutes_spent),
    )

    # If this log is tied to a gap, mark that gap as "improving"
    if gap_id:
        db.execute(
            "UPDATE gaps SET status = 'improving', updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ? AND status = 'open'",
            (gap_id, user_id),
        )

    # ---- Streak logic ----
    streak_row = db.execute(
        "SELECT * FROM streaks WHERE user_id = ?", (user_id,)
    ).fetchone()

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    current_streak = streak_row["current_streak"] if streak_row else 0
    longest_streak = streak_row["longest_streak"] if streak_row else 0
    last_log_date = streak_row["last_log_date"] if streak_row else None

    if last_log_date == today:
        pass  # already logged today, streak unchanged
    elif last_log_date == yesterday:
        current_streak += 1
    else:
        current_streak = 1  # streak broken or first ever log

    longest_streak = max(longest_streak, current_streak)

    db.execute(
        "UPDATE streaks SET current_streak = ?, longest_streak = ?, last_log_date = ? "
        "WHERE user_id = ?",
        (current_streak, longest_streak, today, user_id),
    )
    db.commit()

    return jsonify({
        "message": "Logged.",
        "current_streak": current_streak,
        "longest_streak": longest_streak,
    }), 201


@app.route("/api/logs", methods=["GET"])
@login_required
def get_logs():
    db = get_db()
    user_id = session["user_id"]
    rows = db.execute(
        "SELECT dl.id, dl.log_date, dl.activity, dl.minutes_spent, g.gap_description "
        "FROM daily_logs dl "
        "LEFT JOIN gaps g ON dl.gap_id = g.id "
        "WHERE dl.user_id = ? ORDER BY dl.created_at DESC LIMIT 20",
        (user_id,),
    ).fetchall()

    streak_row = db.execute(
        "SELECT current_streak, longest_streak FROM streaks WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    return jsonify({
        "logs": [dict(row) for row in rows],
        "current_streak": streak_row["current_streak"] if streak_row else 0,
        "longest_streak": streak_row["longest_streak"] if streak_row else 0,
    }), 200


# ---------- MENTOR GUIDANCE ----------

@app.route("/api/guidance", methods=["GET"])
@login_required
def get_guidance():
    db = get_db()
    user_id = session["user_id"]

    open_gaps = db.execute(
        "SELECT target_name, gap_description, status FROM gaps "
        "WHERE user_id = ? AND status != 'closed' ORDER BY created_at DESC LIMIT 10",
        (user_id,),
    ).fetchall()

    recent_logs = db.execute(
        "SELECT log_date, activity FROM daily_logs "
        "WHERE user_id = ? ORDER BY created_at DESC LIMIT 7",
        (user_id,),
    ).fetchall()

    streak_row = db.execute(
        "SELECT current_streak FROM streaks WHERE user_id = ?", (user_id,)
    ).fetchone()

    if not open_gaps and not recent_logs:
        return jsonify({
            "guidance": "You haven't run a Readiness Analysis or logged any practice yet. "
                        "Start with the Readiness Analyzer to find your gaps, then come back here."
        }), 200

    gaps_text = "\n".join(
        f"- [{g['target_name']}] {g['gap_description']} (status: {g['status']})" for g in open_gaps
    ) or "No open gaps recorded."

    logs_text = "\n".join(
        f"- {l['log_date']}: {l['activity']}" for l in recent_logs
    ) or "No practice logged yet."

    current_streak = streak_row["current_streak"] if streak_row else 0

    system_prompt = (
        "You are a supportive, direct personal mentor for a beginner CS student in India "
        "preparing for internships/placements/hackathons. Given their current open gaps and "
        "their recent practice log, tell them clearly and specifically what to focus on next. "
        "Be concrete (name topics, suggest a number of problems or a specific action), keep it "
        "to 4-6 sentences, and be encouraging but honest — don't just say 'keep going,' say "
        "exactly what to do today or this week. Respond in plain text, no markdown."
    )

    user_prompt = (
        f"Current streak: {current_streak} days\n\n"
        f"Open gaps:\n{gaps_text}\n\n"
        f"Recent practice log (last 7 entries):\n{logs_text}\n\n"
        "Based on this, tell the student exactly what to focus on next."
    )

    try:
        gemini_payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
        }
        gemini_response = requests.post(GEMINI_URL, json=gemini_payload, timeout=30)
        gemini_response.raise_for_status()
        guidance_text = gemini_response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return jsonify({"error": f"AI request failed: {str(e)}"}), 502

    return jsonify({"guidance": guidance_text}), 200


# ---------- DOUBT SOLVER ----------

DOUBT_SOLVER_SYSTEM_PROMPT = (
    "You are a warm, patient mentor helping a beginner CS student in India who has "
    "little to no prior programming background and no senior/mentor to ask questions to. "
    "They may ask about placements, internships, hackathons, DSA concepts, career terms, "
    "or general confusion about how the tech industry works. "
    "Explain simply, avoid unexplained jargon, keep answers concise (3-6 sentences unless "
    "the question truly needs more), and be honest about difficulty rather than falsely "
    "reassuring. If the question is unclear, make a reasonable interpretation and answer it "
    "rather than just asking for clarification. Respond in plain text, no markdown headers."
)


@app.route("/api/ask", methods=["POST"])
@login_required
def ask_doubt():
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "Please type a question."}), 400

    try:
        gemini_payload = {
            "systemInstruction": {"parts": [{"text": DOUBT_SOLVER_SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": question}]}],
        }
        gemini_response = requests.post(GEMINI_URL, json=gemini_payload, timeout=30)
        gemini_response.raise_for_status()
        answer = gemini_response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return jsonify({"error": f"AI request failed: {str(e)}"}), 502

    db = get_db()
    user_id = session["user_id"]
    cursor = db.execute(
        "INSERT INTO questions (user_id, question, answer) VALUES (?, ?, ?)",
        (user_id, question, answer),
    )
    db.commit()

    return jsonify({
        "id": cursor.lastrowid,
        "question": question,
        "answer": answer,
    }), 201


@app.route("/api/questions", methods=["GET"])
@login_required
def get_questions():
    db = get_db()
    user_id = session["user_id"]
    rows = db.execute(
        "SELECT id, question, answer, created_at FROM questions "
        "WHERE user_id = ? ORDER BY created_at DESC LIMIT 30",
        (user_id,),
    ).fetchall()
    return jsonify([dict(row) for row in rows]), 200


# ---------- PAGE ROUTES ----------

@app.route("/")
def index():
    return render_template("index.html")


# ---------- ENTRY POINT ----------

if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True, port=5000)