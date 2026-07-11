"""
Task Manager API — Flask + SQLite + JWT auth with roles (admin/user)
Run: python app.py
Test: see test_requests.py
"""
from flask import Flask, request, jsonify, g
import jwt, datetime, os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor
import psycopg2
app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-me"

def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
            host="localhost",
            database="your db name",
            user="user name",
            password="password",
            cursor_factory=RealDictCursor,
        )
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = psycopg2.connect(
        host="localhost",
        database="your db name",
        user="user name",
        password="password",
    )

    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'user'
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            title VARCHAR(255) NOT NULL,
            description TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed token"}), 401
        token = auth.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        g.user_id = payload["user_id"]
        g.role = payload["role"]
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if g.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "user")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, generate_password_hash(password), role),
        )
        db.commit()
    except psycopg2.IntegrityError:
        db.rollback()
        return jsonify({"error": "username already exists"}), 409
    finally:
        cur.close()
    return jsonify({"message": "user created"}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    username = data.get("username")
    password = data.get("password")
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM users WHERE username = %s",
        (username,)
    )
    user = cur.fetchone()
    cur.close()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = jwt.encode(
        {
            "user_id": user["id"],
            "role": user["role"],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=6),
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    return jsonify({"token": token, "role": user["role"]})


@app.route("/api/tasks", methods=["POST"])
@token_required
def create_task():
    print(vars(g))
    data = request.get_json(force=True)
    title = data.get("title")
    if not title:
        return jsonify({"error": "title required"}), 400
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO tasks
        (user_id, title, description, status, created_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            g.user_id,
            title,
            data.get("description", ""),
            "pending",
            datetime.datetime.utcnow(),
        ),
    )
    task_id = cur.fetchone()["id"]
    db.commit()
    cur.close()
    return jsonify({"id": task_id, "message": "task created"}), 201


@app.route("/api/tasks", methods=["GET"])
@token_required
def list_tasks():
    db = get_db()
    cur = db.cursor()
    if g.role == "admin":
        cur.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        )
    else:
        cur.execute(
            "SELECT * FROM tasks WHERE user_id = %s ORDER BY created_at DESC",
            (g.user_id,),
        )
    rows = cur.fetchall()
    cur.close()
    return jsonify(rows)


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
@token_required
def update_task(task_id):

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM tasks WHERE id = %s",
        (task_id,),
    )
    task = cur.fetchone()
    if not task:
        cur.close()
        return jsonify({"error": "not found"}), 404
    if task["user_id"] != g.user_id and g.role != "admin":
        cur.close()
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json(force=True)
    status = data.get("status", task["status"])
    cur.execute(
        "UPDATE tasks SET status=%s WHERE id=%s",
        (status, task_id),
    )
    db.commit()
    cur.close()
    return jsonify({"message": "updated"})


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@token_required
@admin_required
def delete_task(task_id):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "DELETE FROM tasks WHERE id=%s",
        (task_id,),
    )
    db.commit()
    cur.close()
    return jsonify({"message": "deleted"})

@app.route("/")
def home():
    return "Task Manager API is running!"
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
