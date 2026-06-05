import importlib
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = "sqlite:///./test_fileshare.db"
DB_PATH = Path("test_fileshare.db")
if DB_PATH.exists():
    DB_PATH.unlink()

from app.database import SessionLocal
from app.models import StoredFile

main = importlib.import_module("app.main")
client = TestClient(main.app)


def teardown_module(module):
    if DB_PATH.exists():
        DB_PATH.unlink()


def test_register_login_upload_download_flow():
    register = client.post(
        "/register",
        data={"username": "lanuser", "password": "secure123"},
        follow_redirects=False,
    )
    assert register.status_code == 303

    login = client.post(
        "/login",
        data={"username": "lanuser", "password": "secure123"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert "fileshare_user" in login.cookies

    session_cookie = {"fileshare_user": login.cookies["fileshare_user"]}
    upload = client.post(
        "/upload",
        files={"file": ("test.txt", b"airgapped upload", "text/plain")},
        cookies=session_cookie,
        follow_redirects=False,
    )
    assert upload.status_code == 303

    home = client.get("/", cookies=session_cookie)
    assert "test.txt" in home.text

    with SessionLocal() as db:
        row = db.query(StoredFile.id).order_by(StoredFile.id.desc()).first()
    assert row is not None
    file_id = row[0]

    download = client.get(f"/download/{file_id}", cookies=session_cookie)
    assert download.status_code == 200
    assert download.content == b"airgapped upload"
