"""
Korea AV Ethics Platform  (코리아 자율주행 윤리 플랫폼)
-----------------------------------------------------
A Moral-Machine-style web app, localized for South Korea, extended with
free-text NLP so we capture *why* people choose what they choose, not just
the click. Structure mirrors the reference Flask project:
  - session-based auth backed by SQLite
  - a background worker thread (here: re-aggregating NLP insights on a timer,
    instead of a scraper)
  - a small JSON API layer the frontend (and any dashboard) can poll
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import sqlite3
import os
import re
import json
import random
import threading
import time
import secrets
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

from scenarios.scenario_engine import ScenarioEngine
from nlp.insights import analyze_comment, aggregate_insights

# ---------------------------------------------------------------------------
# App / paths
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("APP_SECRET_KEY", secrets.token_hex(32))

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

USER_DB = os.path.join(DATA_DIR, "users.db")
RESPONSE_DB = os.path.join(DATA_DIR, "responses.db")
INSIGHTS_CACHE = os.path.join(DATA_DIR, "insights_cache.json")

engine = ScenarioEngine()

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*a, **kw)
    return wrapped


def is_valid_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True


def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email or "") is not None


# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------
def init_user_db():
    conn = sqlite3.connect(USER_DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            region TEXT,              -- 시/도 (province/city), optional, self-reported
            age_group TEXT,           -- optional bucket, self-reported
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def init_response_db():
    conn = sqlite3.connect(RESPONSE_DB)
    c = conn.cursor()
    # One row per dilemma judged
    c.execute("""
        CREATE TABLE IF NOT EXISTS judgments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_uuid TEXT,
            scenario_id TEXT,
            scenario_json TEXT,
            choice TEXT,               -- 'A' or 'B'
            decision_time_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Free-text reasoning / comments, the NLP-facing table
    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_uuid TEXT,
            scenario_id TEXT,
            judgment_id INTEGER,
            raw_text TEXT,
            lang TEXT DEFAULT 'ko',
            sentiment_label TEXT,
            sentiment_score REAL,
            keywords TEXT,             -- JSON list
            values_detected TEXT,      -- JSON list, e.g. ["utilitarian","legal_status","age"]
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # End-of-session summary (like Moral Machine's "your results" screen)
    c.execute("""
        CREATE TABLE IF NOT EXISTS session_summary (
            session_uuid TEXT PRIMARY KEY,
            user_id INTEGER,
            saved_more TEXT,          -- JSON: character -> saved count
            characteristic_weights TEXT, -- JSON: computed preference weights
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


init_user_db()
init_response_db()


# ---------------------------------------------------------------------------
# Background worker: periodically re-aggregate NLP insights into a cache file
# (mirrors the reference project's "scraper + sentiment pipeline every 30 min"
#  background thread, just pointed at our own response DB instead of the web)
# ---------------------------------------------------------------------------
def refresh_insights_loop():
    while True:
        try:
            print("[insights] refreshing aggregate NLP insights...")
            summary = aggregate_insights(RESPONSE_DB)
            with open(INSIGHTS_CACHE, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print("[insights] done.")
        except Exception as e:
            print(f"[insights] error: {e}")
        time.sleep(300)  # every 5 minutes


threading.Thread(target=refresh_insights_loop, daemon=True).start()


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("mainpage"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("mainpage"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        username = request.form.get("username")
        region = request.form.get("region")
        age_group = request.form.get("age_group")

        if not all([email, password, confirm_password, username]):
            flash("모든 필드를 입력해주세요 (All fields are required)", "error")
            return render_template("register.html")
        if not is_valid_email(email):
            flash("이메일 형식이 올바르지 않습니다", "error")
            return render_template("register.html")
        if password != confirm_password:
            flash("비밀번호가 일치하지 않습니다", "error")
            return render_template("register.html")
        if not is_valid_password(password):
            flash("비밀번호는 8자 이상, 대/소문자, 숫자, 특수문자를 포함해야 합니다", "error")
            return render_template("register.html")

        conn = sqlite3.connect(USER_DB)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        if c.fetchone():
            conn.close()
            flash("이미 등록된 이메일입니다", "error")
            return render_template("register.html")

        c.execute(
            "INSERT INTO users (email, password_hash, name, region, age_group) VALUES (?, ?, ?, ?, ?)",
            (email, generate_password_hash(password), username, region, age_group),
        )
        conn.commit()
        conn.close()
        flash("회원가입 완료! 로그인 해주세요.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = sqlite3.connect(USER_DB)
        c = conn.cursor()
        c.execute("SELECT id, password_hash, name FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["user_name"] = user[2]
            session["session_uuid"] = secrets.token_hex(16)

            conn = sqlite3.connect(USER_DB)
            c = conn.cursor()
            c.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user[0],))
            conn.commit()
            conn.close()

            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("mainpage"))
        flash("이메일 또는 비밀번호가 올바르지 않습니다", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("로그아웃 되었습니다", "info")
    return redirect(url_for("login"))


@app.route("/guest")
def guest():
    """Moral Machine lets people play without an account - support that too."""
    session["user_id"] = None
    session["user_name"] = "Guest"
    session["session_uuid"] = secrets.token_hex(16)
    return redirect(url_for("mainpage"))


# ---------------------------------------------------------------------------
# Core app routes
# ---------------------------------------------------------------------------
@app.route("/mainpage")
@login_required
def mainpage():
    return render_template("mainpage.html", user_name=session.get("user_name"))


@app.route("/judge")
@login_required
def judge():
    """The core Moral-Machine-style dilemma screen."""
    scenario = engine.generate_scenario()
    return render_template("judge.html", scenario=scenario, user_name=session.get("user_name"))


@app.route("/api/scenario")
@login_required
def api_scenario():
    return jsonify(engine.generate_scenario())


@app.route("/api/judgment", methods=["POST"])
@login_required
def api_judgment():
    payload = request.get_json(force=True)
    conn = sqlite3.connect(RESPONSE_DB)
    c = conn.cursor()
    c.execute(
        """INSERT INTO judgments
           (user_id, session_uuid, scenario_id, scenario_json, choice, decision_time_ms)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session.get("user_id"),
            session.get("session_uuid"),
            payload.get("scenario_id"),
            json.dumps(payload.get("scenario"), ensure_ascii=False),
            payload.get("choice"),
            payload.get("decision_time_ms"),
        ),
    )
    judgment_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "judgment_id": judgment_id})


@app.route("/api/comment", methods=["POST"])
@login_required
def api_comment():
    """This is the NLP-facing endpoint: 'why did you choose that?'"""
    payload = request.get_json(force=True)
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"status": "skipped", "reason": "empty"}), 200

    analysis = analyze_comment(text)

    conn = sqlite3.connect(RESPONSE_DB)
    c = conn.cursor()
    c.execute(
        """INSERT INTO comments
           (user_id, session_uuid, scenario_id, judgment_id, raw_text, lang,
            sentiment_label, sentiment_score, keywords, values_detected)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session.get("user_id"),
            session.get("session_uuid"),
            payload.get("scenario_id"),
            payload.get("judgment_id"),
            text,
            analysis["lang"],
            analysis["sentiment_label"],
            analysis["sentiment_score"],
            json.dumps(analysis["keywords"], ensure_ascii=False),
            json.dumps(analysis["values_detected"], ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "analysis": analysis})


@app.route("/results")
@login_required
def results():
    """End-of-session personal results, like Moral Machine's results page."""
    conn = sqlite3.connect(RESPONSE_DB)
    c = conn.cursor()
    c.execute(
        "SELECT scenario_json, choice FROM judgments WHERE session_uuid = ? ORDER BY id",
        (session.get("session_uuid"),),
    )
    rows = c.fetchall()
    conn.close()

    from scenarios.scenario_engine import compute_preference_weights
    weights = compute_preference_weights(rows)
    return render_template("results.html", weights=weights, total=len(rows))


@app.route("/insights")
@login_required
def insights_dashboard():
    """Aggregate, anonymized public dashboard: NLP insights across all users."""
    if os.path.exists(INSIGHTS_CACHE):
        with open(INSIGHTS_CACHE, "r", encoding="utf-8") as f:
            summary = json.load(f)
    else:
        summary = aggregate_insights(RESPONSE_DB)
    return render_template("insights.html", summary=summary)


@app.route("/api/insights")
@login_required
def api_insights():
    return jsonify(aggregate_insights(RESPONSE_DB))


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
