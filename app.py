from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "learnhub-secret-key-2026"

DATABASE = "learnhub.db"


# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS publishers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            brand_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            publisher_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# SIMPLE HELPER FUNCTIONS
# ─────────────────────────────────────────────

def get_logged_in_user():
    # Returns the email of the person logged in, or None
    return session.get("user")


def get_publisher_by_email(email):
    # Looks up the publisher for this email and returns it, or None
    conn = get_db()
    publisher = conn.execute(
        "SELECT * FROM publishers WHERE user_email = ?", (email,)
    ).fetchone()
    conn.close()
    return publisher


# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("home.html")

    # Read what the user typed in the form
    first = request.form.get("first_name", "").strip()
    last = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    # If fields are empty...
    if not first or not last or not email or not password:
        flash("Please fill in all fields.", "warning")
        return redirect(url_for("signup"))

    conn = get_db()

    # Check if this email is already registered
    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()

    if existing:
        conn.close()
        flash("An account with that email already exists.", "warning")
        return redirect(url_for("login"))

    # Save the new user with a hashed password
    conn.execute(
        "INSERT INTO users (first_name, last_name, email, password) VALUES (?, ?, ?, ?)",
        (first, last, email, generate_password_hash(password))
    )
    conn.commit()
    conn.close()

    # Log them in straight away
    session["user"] = email
    flash("Account created successfully!", "success")
    return redirect(url_for("home"))

    # Login in 
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("log_in.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    # Check if the user exists and the password is correct
    if user and check_password_hash(user["password"], password):
        session["user"] = email
        flash("Logged in successfully!", "success")
        return redirect(url_for("home"))

    flash("Wrong email or password. Please try again.", "danger")
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ─────────────────────────────────────────────
# HOME — LEARNER VIEW
# ─────────────────────────────────────────────

@app.route("/home")
def home():
    # Check the user is logged in
    email = get_logged_in_user()
    if not email:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    # Get all courses from the database, with the publisher's brand name
    conn = get_db()
    all_courses = conn.execute("""
        SELECT courses.id, courses.name, courses.description,
               courses.category, courses.price, publishers.brand_name
        FROM courses
        JOIN publishers ON courses.publisher_id = publishers.id
        ORDER BY courses.category, courses.id
    """).fetchall()
    conn.close()

    # Group the courses by their category
    courses_by_category = {}
    for course in all_courses:
        cat = course["category"]
        if cat not in courses_by_category:
            courses_by_category[cat] = []
        courses_by_category[cat].append(dict(course))

    return render_template("home.html", user=email, courses_by_category=courses_by_category)


# ─────────────────────────────────────────────
# PUBLISHER ROUTES
# ─────────────────────────────────────────────

@app.route("/register_publisher", methods=["GET", "POST"])
def register_publisher():
    # Check login
    email = get_logged_in_user()
    if not email:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    # If they already have a publisher account, send them to the dashboard
    if get_publisher_by_email(email):
        return redirect(url_for("publisher_dashboard"))

    if request.method == "GET":
        return render_template("register_publisher.html")

    # Read the form
    full_name = request.form.get("fullname", "").strip()
    brand_name = request.form.get("businessname", "").strip()
    pub_email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()

    # Make sure all fields are filled
    if not full_name or not brand_name or not pub_email or not phone:
        flash("Please fill in all fields.", "warning")
        return redirect(url_for("register_publisher"))

    # Save the publisher account
    conn = get_db()
    conn.execute("""
        INSERT INTO publishers (user_email, full_name, brand_name, email, phone)
        VALUES (?, ?, ?, ?, ?)
    """, (email, full_name, brand_name, pub_email, phone))
    conn.commit()
    conn.close()

    flash("Publisher account created!", "success")
    return redirect(url_for("publisher_dashboard"))


@app.route("/publisher_dashboard", methods=["GET", "POST"])
def publisher_dashboard():
    # Check login
    email = get_logged_in_user()
    if not email:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    # Check they have a publisher account
    publisher = get_publisher_by_email(email)
    if not publisher:
        flash("You need a publisher account first.", "warning")
        return redirect(url_for("register_publisher"))

    # If the form was submitted, create a new course
    if request.method == "POST":
        name = request.form.get("course_name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        price_text = request.form.get("price", "").strip()

        # Check all fields are filled
        if not name or not description or not category or not price_text:
            flash("Please fill in all course fields.", "warning")
            return redirect(url_for("publisher_dashboard"))

        # Make sure the price is a valid number
        try:
            price = float(price_text)
            if price < 0:
                raise ValueError
        except ValueError:
            flash("Price must be a valid number (0 or above).", "warning")
            return redirect(url_for("publisher_dashboard"))

        # Save the course
        conn = get_db()
        conn.execute("""
            INSERT INTO courses (publisher_id, name, description, category, price)
            VALUES (?, ?, ?, ?, ?)
        """, (publisher["id"], name, description, category, price))
        conn.commit()
        conn.close()

        flash("Course published!", "success")
        return redirect(url_for("publisher_dashboard"))

    # Load all courses for this publisher
    conn = get_db()
    courses = conn.execute(
        "SELECT * FROM courses WHERE publisher_id = ? ORDER BY id DESC",
        (publisher["id"],)
    ).fetchall()
    conn.close()

    # Count courses and total value
    course_count = len(courses)
    total_value = sum(c["price"] for c in courses if c["price"])

    return render_template(
        "publisher_dashboard.html",
        publisher=publisher,
        courses=courses,
        course_count=course_count,
        total_earnings=total_value
    )


@app.route("/delete_course/<int:course_id>", methods=["POST"])
def delete_course(course_id):
    email = get_logged_in_user()
    if not email:
        return redirect(url_for("login"))

    publisher = get_publisher_by_email(email)
    if not publisher:
        return redirect(url_for("register_publisher"))

    # Delete the course only if it belongs to this publisher
    conn = get_db()
    conn.execute(
        "DELETE FROM courses WHERE id = ? AND publisher_id = ?",
        (course_id, publisher["id"])
    )
    conn.commit()
    conn.close()

    flash("Course deleted.", "info")
    return redirect(url_for("publisher_dashboard"))


@app.route("/edit_course/<int:course_id>", methods=["POST"])
def edit_course(course_id):
    email = get_logged_in_user()
    if not email:
        return redirect(url_for("login"))

    publisher = get_publisher_by_email(email)
    if not publisher:
        return redirect(url_for("register_publisher"))

    name = request.form.get("course_name", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    price_text = request.form.get("price", "").strip()

    if not name or not description or not category or not price_text:
        flash("Please fill in all fields.", "warning")
        return redirect(url_for("publisher_dashboard"))

    try:
        price = float(price_text)
        if price < 0:
            raise ValueError
    except ValueError:
        flash("Price must be a valid number.", "warning")
        return redirect(url_for("publisher_dashboard"))

    # Update the course only if it belongs to this publisher
    conn = get_db()
    conn.execute("""
        UPDATE courses
        SET name = ?, description = ?, category = ?, price = ?
        WHERE id = ? AND publisher_id = ?
    """, (name, description, category, price, course_id, publisher["id"]))
    conn.commit()
    conn.close()

    flash("Course updated!", "success")
    return redirect(url_for("publisher_dashboard"))


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
