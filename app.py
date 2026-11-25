import hmac
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from email.message import EmailMessage
from email.utils import parseaddr
from functools import wraps
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import RequestEntityTooLarge


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

INITIAL_DOCTORS = (
    ("Dr. Arjun Sharma", "General Medicine", "MBBS, MD · General Physician", 12, 4.9),
    ("Dr. Neha Kapoor", "Cardiology", "MBBS, MD, DM · Cardiologist", 10, 4.9),
    ("Dr. Rohan Mehta", "Orthopedics", "MBBS, MS · Orthopedic Specialist", 14, 4.8),
    ("Dr. Riya Mehta", "Pediatrics", "MBBS, MD · Pediatrician", 8, 4.9),
)
ALLOWED_IMAGE_FORMATS = {
    "JPEG": ("jpg", "JPEG"),
    "PNG": ("png", "PNG"),
    "WEBP": ("webp", "WEBP"),
}
PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]{10,15}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.getenv("DATABASE_PATH", str(ROOT / "data" / "clinic.sqlite3")),
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", str(ROOT / "uploads")),
        ADMIN_USERNAME=os.getenv("ADMIN_USERNAME", ""),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", ""),
        ADMIN_EMAIL=os.getenv("ADMIN_EMAIL", ""),
        SMTP_HOST=os.getenv("SMTP_HOST", ""),
        SMTP_PORT=int(os.getenv("SMTP_PORT", "587")),
        SMTP_USERNAME=os.getenv("SMTP_USERNAME", ""),
        SMTP_PASSWORD=os.getenv("SMTP_PASSWORD", ""),
        SMTP_FROM=os.getenv("SMTP_FROM", ""),
        SMTP_USE_TLS=env_bool("SMTP_USE_TLS", True),
        SMTP_USE_SSL=env_bool("SMTP_USE_SSL"),
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=env_bool("COOKIE_SECURE"),
    )
    if test_config:
        app.config.update(test_config)

    app.extensions["email_executor"] = ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix="clinic-email",
    )

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    initialize_database(app)

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        if request.path.startswith("/api/"):
            return jsonify(error="The uploaded request is too large."), 413
        flash("The uploaded image is too large. Maximum upload size is 5 MB.", "error")
        target = "admin" if session.get("admin_authenticated") else "admin_login"
        return redirect(url_for(target))

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": csrf_token}

    @app.get("/")
    def home():
        return send_from_directory(ROOT, "index.html")

    @app.get("/style.css")
    def stylesheet():
        return send_from_directory(ROOT, "style.css")

    @app.get("/script.js")
    def javascript():
        return send_from_directory(ROOT, "script.js")

    @app.get("/uploads/<path:filename>")
    def uploaded_image(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.get("/api/doctors")
    def doctors_api():
        with database_connection() as db:
            doctors = db.execute(
                "SELECT id, name, specialty, qualifications, years_experience, "
                "rating, bio, image_filename FROM doctors ORDER BY id"
            ).fetchall()
        return jsonify(
            [
                {
                    "id": doctor["id"],
                    "name": doctor["name"],
                    "specialty": doctor["specialty"],
                    "qualifications": doctor["qualifications"],
                    "years_experience": doctor["years_experience"],
                    "rating": doctor["rating"],
                    "bio": doctor["bio"],
                    "image_url": (
                        url_for("uploaded_image", filename=doctor["image_filename"])
                        if doctor["image_filename"]
                        else None
                    ),
                }
                for doctor in doctors
            ]
        )

    @app.post("/api/enquiries")
    def enquiry_api():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Please submit the form using the website."), 400

        name = clean_text(payload.get("name"), 100)
        patient_email = clean_text(payload.get("email"), 254)
        phone = clean_text(payload.get("phone"), 30)
        specialty = clean_text(payload.get("specialty"), 100)
        appointment_date = clean_text(payload.get("date"), 10)
        message = clean_text(payload.get("message"), 2000)
        if not name or len(name) < 2 or len(name) > 100:
            return jsonify(error="Please enter your full name."), 400
        parsed_name, parsed_email = parseaddr(patient_email)
        if (
            not patient_email
            or len(patient_email) > 254
            or not EMAIL_PATTERN.fullmatch(patient_email)
            or parsed_name
            or parsed_email.lower() != patient_email.lower()
        ):
            return jsonify(error="Please enter a valid email address."), 400
        if not phone or not PHONE_PATTERN.fullmatch(phone):
            return jsonify(error="Please enter a valid phone number."), 400
        if not specialty or len(specialty) > 100 or not appointment_date:
            return jsonify(error="Please select a specialty and preferred date."), 400
        try:
            selected_date = date.fromisoformat(appointment_date)
        except ValueError:
            return jsonify(error="Please select a valid appointment date."), 400
        if selected_date < date.today():
            return jsonify(error="Please select today or a future date."), 400
        if len(message) > 2000:
            return jsonify(error="Please shorten your message and try again."), 400

        try:
            validate_email_configuration(app)
            executor = app.extensions["email_executor"]
            future = executor.submit(
                send_enquiry_email,
                app,
                name,
                patient_email,
                phone,
                specialty,
                appointment_date,
                message,
            )
            future.add_done_callback(
                lambda completed: log_email_delivery_failure(app, completed)
            )
        except (ValueError, RuntimeError):
            app.logger.exception("Could not queue appointment enquiry email")
            return (
                jsonify(
                    error="We couldn't queue your request right now. Please call the clinic."
                ),
                503,
            )
        return (
            jsonify(
                message="Your request was received. Our team will contact you shortly."
            ),
            202,
        )

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            if not valid_csrf_token():
                abort(400, "Invalid form token. Please refresh and try again.")
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            configured_username = app.config["ADMIN_USERNAME"]
            configured_password = app.config["ADMIN_PASSWORD"]
            if not configured_username or not configured_password:
                app.logger.error("Admin login is disabled: credentials are not configured")
                abort(503, "Admin login is not configured.")
            if not (
                hmac.compare_digest(username, configured_username)
                and hmac.compare_digest(password, configured_password)
            ):
                flash("Invalid username or password.", "error")
            else:
                session.clear()
                session["admin_authenticated"] = True
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("admin"))
        return render_template("admin_login.html")

    @app.post("/admin/logout")
    @admin_required
    def admin_logout():
        require_csrf()
        session.clear()
        return redirect(url_for("admin_login"))

    @app.get("/admin")
    @admin_required
    def admin():
        with database_connection() as db:
            doctors = db.execute("SELECT * FROM doctors ORDER BY name").fetchall()
        return render_template("admin.html", doctors=doctors, doctor=None)

    @app.route("/admin/doctors/add", methods=["POST"])
    @admin_required
    def add_doctor():
        require_csrf()
        values, error = doctor_form_values()
        if error:
            flash(error, "error")
            return redirect(url_for("admin"))
        try:
            image_filename = save_uploaded_image(request.files.get("image"))
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("admin"))
        with database_connection() as db:
            db.execute(
                "INSERT INTO doctors "
                "(name, specialty, qualifications, years_experience, rating, bio, image_filename) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (*values, image_filename),
            )
        flash("Doctor added.", "success")
        return redirect(url_for("admin"))

    @app.route("/admin/doctors/<int:doctor_id>", methods=["GET", "POST"])
    @admin_required
    def edit_doctor(doctor_id):
        with database_connection() as db:
            doctor = db.execute(
                "SELECT * FROM doctors WHERE id = ?", (doctor_id,)
            ).fetchone()
        if doctor is None:
            abort(404)
        if request.method == "POST":
            require_csrf()
            values, error = doctor_form_values()
            if error:
                flash(error, "error")
                return redirect(url_for("edit_doctor", doctor_id=doctor_id))
            try:
                new_image = save_uploaded_image(request.files.get("image"))
            except ValueError as error:
                flash(str(error), "error")
                return redirect(url_for("edit_doctor", doctor_id=doctor_id))
            image_filename = new_image or doctor["image_filename"]
            with database_connection() as db:
                db.execute(
                    "UPDATE doctors SET name = ?, specialty = ?, qualifications = ?, "
                    "years_experience = ?, rating = ?, bio = ?, image_filename = ? "
                    "WHERE id = ?",
                    (*values, image_filename, doctor_id),
                )
            if new_image and doctor["image_filename"]:
                remove_uploaded_image(doctor["image_filename"])
            flash("Doctor details updated.", "success")
            return redirect(url_for("admin"))
        with database_connection() as db:
            doctors = db.execute("SELECT * FROM doctors ORDER BY name").fetchall()
        return render_template("admin.html", doctors=doctors, doctor=doctor)

    @app.post("/admin/doctors/<int:doctor_id>/delete")
    @admin_required
    def delete_doctor(doctor_id):
        require_csrf()
        with database_connection() as db:
            doctor = db.execute(
                "SELECT image_filename FROM doctors WHERE id = ?", (doctor_id,)
            ).fetchone()
            if doctor is None:
                abort(404)
            db.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
        if doctor["image_filename"]:
            remove_uploaded_image(doctor["image_filename"])
        flash("Doctor removed.", "success")
        return redirect(url_for("admin"))

    return app


def initialize_database(app):
    db = sqlite3.connect(app.config["DATABASE"])
    try:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                specialty TEXT NOT NULL,
                qualifications TEXT NOT NULL,
                years_experience INTEGER NOT NULL,
                rating REAL NOT NULL,
                bio TEXT NOT NULL DEFAULT '',
                image_filename TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS app_metadata "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        seeded = db.execute(
            "SELECT 1 FROM app_metadata WHERE key = 'initial_doctors_seeded'"
        ).fetchone()
        if not seeded:
            db.executemany(
                "INSERT INTO doctors "
                "(name, specialty, qualifications, years_experience, rating) "
                "VALUES (?, ?, ?, ?, ?)",
                INITIAL_DOCTORS,
            )
            db.execute(
                "INSERT INTO app_metadata (key, value) "
                "VALUES ('initial_doctors_seeded', 'true')"
            )
        db.commit()
    finally:
        db.close()


class database_connection:
    def __enter__(self):
        self.db = sqlite3.connect(current_app.config["DATABASE"])
        self.db.row_factory = sqlite3.Row
        return self.db

    def __exit__(self, exception_type, exception, traceback):
        try:
            if exception_type:
                self.db.rollback()
            else:
                self.db.commit()
        finally:
            self.db.close()


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def valid_csrf_token():
    submitted = request.form.get("_csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(expected) and hmac.compare_digest(submitted, expected)


def require_csrf():
    if not valid_csrf_token():
        abort(400, "Invalid form token. Please refresh and try again.")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


def clean_text(value, max_length):
    if not isinstance(value, str):
        return ""
    return value.strip()[: max_length + 1]


def doctor_form_values():
    name = clean_text(request.form.get("name"), 100)
    specialty = clean_text(request.form.get("specialty"), 80)
    qualifications = clean_text(request.form.get("qualifications"), 160)
    bio = clean_text(request.form.get("bio"), 500)
    years = clean_text(request.form.get("years_experience"), 3)
    rating_text = clean_text(request.form.get("rating"), 4)
    if not name or len(name) > 100 or not specialty or len(specialty) > 80:
        return None, "Enter a doctor name (up to 100 characters) and specialty (up to 80)."
    if not qualifications or len(qualifications) > 160 or len(bio) > 500:
        return None, "Enter qualifications (up to 160 characters); the bio can be up to 500."
    try:
        years_experience = int(years)
        rating = float(rating_text)
    except ValueError:
        return None, "Enter a valid number of years and a rating from 0 to 5."
    if not 0 <= years_experience <= 100 or not 0 <= rating <= 5:
        return None, "Years must be 0-100 and rating must be 0-5."
    return (
        (name, specialty, qualifications, years_experience, rating, bio),
        None,
    )


def save_uploaded_image(upload):
    if not upload or not upload.filename:
        return None
    content = upload.stream.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise RequestEntityTooLarge()
    try:
        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ValueError("Use a JPG, PNG, or WEBP image.")
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image = ImageOps.exif_transpose(image)
            if image.width > 6000 or image.height > 6000:
                raise ValueError("Image dimensions must be 6000 × 6000 pixels or smaller.")
            image.load()
            extension, output_format = ALLOWED_IMAGE_FORMATS[image_format]
            if output_format == "JPEG":
                image = image.convert("RGB")
            elif image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            filename = f"{uuid.uuid4().hex}.{extension}"
            path = Path(current_app.config["UPLOAD_FOLDER"]) / filename
            image.save(path, format=output_format, optimize=True)
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("That file is not a valid JPG, PNG, or WEBP image.") from error
    return filename


def remove_uploaded_image(filename):
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    image_path = (upload_dir / filename).resolve()
    if image_path.parent == upload_dir and image_path.is_file():
        image_path.unlink()


def validate_email_configuration(app):
    config = app.config
    recipient = config["ADMIN_EMAIL"].strip()
    sender = (config["SMTP_FROM"] or config["SMTP_USERNAME"]).strip()
    if not recipient or not config["SMTP_HOST"] or not sender:
        raise ValueError("Admin email, SMTP host, and sender address must be configured.")
    if bool(config["SMTP_USERNAME"]) != bool(config["SMTP_PASSWORD"]):
        raise ValueError("Both SMTP username and password must be configured together.")
    if config["SMTP_USE_SSL"] and config["SMTP_USE_TLS"]:
        raise ValueError("Choose either SMTP SSL or STARTTLS, not both.")


def log_email_delivery_failure(app, future):
    if future.cancelled():
        app.logger.error("Appointment enquiry email was cancelled before delivery")
        return
    error = future.exception()
    if error is not None:
        app.logger.error(
            "Could not deliver appointment enquiry email",
            exc_info=(type(error), error, error.__traceback__),
        )


def send_enquiry_email(
    app, name, patient_email, phone, specialty, appointment_date, message
):
    validate_email_configuration(app)
    config = app.config
    recipient = config["ADMIN_EMAIL"].strip()
    sender = (config["SMTP_FROM"] or config["SMTP_USERNAME"]).strip()

    email = EmailMessage()
    email["Subject"] = "New appointment enquiry - Shivay Clinic"
    email["From"] = sender
    email["To"] = recipient
    email["Reply-To"] = patient_email
    email.set_content(
        "A new appointment enquiry was submitted on the Shivay Clinic website.\n\n"
        f"Name: {name}\n"
        f"Email: {patient_email}\n"
        f"Phone: {phone}\n"
        f"Specialty: {specialty}\n"
        f"Preferred date: {appointment_date}\n"
        f"Message: {message or '(No additional message)'}\n"
    )

    if config["SMTP_USE_SSL"]:
        with smtplib.SMTP_SSL(
            config["SMTP_HOST"], config["SMTP_PORT"], timeout=15
        ) as smtp:
            if config["SMTP_USERNAME"]:
                smtp.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            smtp.send_message(email)
    else:
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=15) as smtp:
            if config["SMTP_USE_TLS"]:
                smtp.starttls()
            if config["SMTP_USERNAME"]:
                smtp.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            smtp.send_message(email)


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=env_bool("FLASK_DEBUG"),
    )
