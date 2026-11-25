import io
import tempfile
import unittest
from concurrent.futures import Future
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app


class QueuedExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, function, *args):
        future = Future()
        self.jobs.append((function, args, future))
        return future

    def run_next(self):
        function, args, future = self.jobs.pop(0)
        future.set_running_or_notify_cancel()
        try:
            result = function(*args)
        except BaseException as error:
            future.set_exception(error)
        else:
            future.set_result(result)


class ClinicAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": str(root / "clinic.sqlite3"),
                "UPLOAD_FOLDER": str(root / "uploads"),
                "ADMIN_USERNAME": "clinic-admin",
                "ADMIN_PASSWORD": "strong-test-password",
                "ADMIN_EMAIL": "admin@example.test",
                "SMTP_HOST": "smtp.example.test",
                "SMTP_PORT": 587,
                "SMTP_USERNAME": "clinic@example.test",
                "SMTP_PASSWORD": "smtp-test-password",
                "SMTP_FROM": "clinic@example.test",
                "SMTP_USE_TLS": True,
            }
        )
        self.client = self.app.test_client()
        self.real_executor = self.app.extensions["email_executor"]
        self.queued_executor = QueuedExecutor()
        self.app.extensions["email_executor"] = self.queued_executor

    def tearDown(self):
        self.real_executor.shutdown(wait=True, cancel_futures=True)
        self.temp_dir.cleanup()

    def login(self):
        response = self.client.get("/admin/login")
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        response = self.client.post(
            "/admin/login",
            data={
                "_csrf_token": token,
                "username": "clinic-admin",
                "password": "strong-test-password",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_doctor_api_starts_with_original_profiles(self):
        response = self.client.get("/api/doctors")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [doctor["name"] for doctor in response.json],
            [
                "Dr. Arjun Sharma",
                "Dr. Neha Kapoor",
                "Dr. Rohan Mehta",
                "Dr. Riya Mehta",
            ],
        )

    def test_appointment_form_includes_required_patient_email(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="patientEmail"', response.data)
        self.assertIn(b'type="email"', response.data)
        self.assertIn(b'required', response.data)
        response.close()

    def test_admin_login_is_required_and_csrf_protected(self):
        self.assertEqual(self.client.get("/admin").status_code, 302)
        self.assertEqual(self.client.post("/admin/login").status_code, 400)
        self.login()
        self.assertEqual(self.client.get("/admin").status_code, 200)

    def test_admin_can_add_and_remove_a_doctor_and_photo(self):
        self.login()
        with self.client.session_transaction() as session:
            token = session["csrf_token"]

        image_data = io.BytesIO()
        Image.new("RGB", (8, 8), color="teal").save(image_data, format="PNG")
        image_data.seek(0)
        response = self.client.post(
            "/admin/doctors/add",
            data={
                "_csrf_token": token,
                "name": "Dr. Test Doctor",
                "specialty": "Dermatology",
                "qualifications": "MBBS · Dermatologist",
                "years_experience": "6",
                "rating": "4.7",
                "bio": "A short profile.",
                "image": (image_data, "doctor.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        doctors = self.client.get("/api/doctors").json
        added = next(item for item in doctors if item["name"] == "Dr. Test Doctor")
        self.assertEqual(added["bio"], "A short profile.")
        image_response = self.client.get(added["image_url"])
        self.assertEqual(image_response.status_code, 200)
        image_response.close()

        response = self.client.post(
            f"/admin/doctors/{added['id']}",
            data={
                "_csrf_token": token,
                "name": "Dr. Updated Doctor",
                "specialty": "Dermatology",
                "qualifications": "MBBS, MD · Consultant",
                "years_experience": "7",
                "rating": "4.8",
                "bio": "Updated profile.",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        updated = next(
            item
            for item in self.client.get("/api/doctors").json
            if item["id"] == added["id"]
        )
        self.assertEqual(updated["name"], "Dr. Updated Doctor")
        self.assertEqual(updated["bio"], "Updated profile.")
        self.assertEqual(updated["image_url"], added["image_url"])

        response = self.client.post(
            f"/admin/doctors/{added['id']}/delete",
            data={"_csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(
            "Dr. Test Doctor",
            [item["name"] for item in self.client.get("/api/doctors").json],
        )
        self.assertFalse(
            list(Path(self.app.config["UPLOAD_FOLDER"]).iterdir())
        )

    def test_enquiry_is_validated_and_emailed(self):
        self.assertEqual(
            self.client.post("/api/enquiries", json={"name": "A"}).status_code,
            400,
        )
        missing_email_response = self.client.post(
            "/api/enquiries",
            json={
                "name": "Asha Patel",
                "phone": "+91 98765 43210",
                "specialty": "Cardiology",
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "message": "Please call me.",
            },
        )
        self.assertEqual(missing_email_response.status_code, 400)
        invalid_email_response = self.client.post(
            "/api/enquiries",
            json={
                "name": "Asha Patel",
                "email": "not-an-email",
                "phone": "+91 98765 43210",
                "specialty": "Cardiology",
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "message": "Please call me.",
            },
        )
        self.assertEqual(invalid_email_response.status_code, 400)

        with patch("app.smtplib.SMTP") as smtp_factory:
            response = self.client.post(
                "/api/enquiries",
                json={
                    "name": "Asha Patel",
                    "email": "asha@example.test",
                    "phone": "+91 98765 43210",
                    "specialty": "Cardiology",
                    "date": (date.today() + timedelta(days=1)).isoformat(),
                    "message": "Please call me.",
                },
            )

            self.assertEqual(response.status_code, 202)
            self.assertIn("received", response.json["message"])
            self.assertEqual(len(self.queued_executor.jobs), 1)
            self.assertFalse(self.queued_executor.jobs[0][2].done())
            self.queued_executor.run_next()

        smtp = smtp_factory.return_value.__enter__.return_value
        smtp.send_message.assert_called_once()
        sent_email = smtp.send_message.call_args.args[0]
        self.assertEqual(sent_email["To"], "admin@example.test")
        self.assertEqual(sent_email["Reply-To"], "asha@example.test")
        self.assertIn("Email: asha@example.test", sent_email.get_content())
        self.assertIn("Please call me.", sent_email.get_content())

    def test_smtp_failure_is_logged_in_background_after_request_is_accepted(self):
        response = self.client.post(
            "/api/enquiries",
            json={
                "name": "Asha Patel",
                "email": "asha@example.test",
                "phone": "+91 98765 43210",
                "specialty": "Cardiology",
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "message": "Please call me.",
            },
        )
        self.assertEqual(response.status_code, 202)

        with patch("app.smtplib.SMTP") as smtp_factory:
            smtp_factory.return_value.__enter__.return_value.starttls.side_effect = (
                OSError("SMTP unavailable")
            )
            with self.assertLogs(self.app.logger, level="ERROR"):
                self.queued_executor.run_next()

    def test_enquiry_reports_missing_smtp_configuration(self):
        self.app.config["SMTP_HOST"] = ""
        response = self.client.post(
            "/api/enquiries",
            json={
                "name": "Asha Patel",
                "email": "asha@example.test",
                "phone": "+91 98765 43210",
                "specialty": "Cardiology",
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "message": "",
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("couldn't queue", response.json["error"])


if __name__ == "__main__":
    unittest.main()
