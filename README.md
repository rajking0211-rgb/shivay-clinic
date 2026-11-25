# Shivay Clinic website backend

The website is served by Flask. The existing doctor profiles are seeded into a
local SQLite database the first time the app starts. Use the doctor admin page
to add, edit, or remove profiles and upload JPG, PNG, or WEBP profile photos.
Appointment requests are validated by the server and emailed to `ADMIN_EMAIL`.
The appointment form asks for the patient's email address; messages use the
configured clinic sender and set the patient's address as `Reply-To`. SMTP
delivery runs in a small background thread pool so the form response does not
wait for the mail server. Delivery failures are recorded in the Flask server
log, so keep the SMTP configuration valid and monitor those logs.

## Run locally

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment, then install dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set a unique `SECRET_KEY`, strong admin
   credentials, the clinic's `ADMIN_EMAIL`, and working SMTP settings. Use an
   email provider's app password rather than an account password where
   applicable. Enquiries cannot be sent until the SMTP values are configured.
4. Start the server:

   ```powershell
   python app.py
   ```

5. Visit `http://127.0.0.1:5000/`. The protected management page is at
   `http://127.0.0.1:5000/admin/login`.

SQLite data is stored in `data/clinic.sqlite3`; uploaded profile images are
stored in `uploads/`. Back up both directories. Keep `.env` private. In
production, run behind HTTPS, set `COOKIE_SECURE=true`, use a production WSGI
server, and set a stable random `SECRET_KEY`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Signs secure Flask session cookies; keep it stable and private. |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Single administrator credentials. |
| `ADMIN_EMAIL` | Recipient of new appointment requests. |
| `SMTP_HOST`, `SMTP_PORT` | Outgoing mail server and port. |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Optional SMTP authentication; set both or neither. |
| `SMTP_FROM` | Sender address; defaults to `SMTP_USERNAME`. |
| `SMTP_USE_TLS`, `SMTP_USE_SSL` | Use STARTTLS (default) or implicit TLS. |
| `COOKIE_SECURE` | Require HTTPS for the admin session cookie. |

`DATABASE_PATH` and `UPLOAD_FOLDER` can be set to choose persistent storage
locations.
