import os
import re
import warnings
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import StoredFile, User

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fileshare LAN")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SESSION_COOKIE = "fileshare_user"
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "86400"))
SESSION_SECURE = os.getenv("SESSION_SECURE", "false").lower() == "true"
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))

if SESSION_SECRET == "change-me-in-production":
    warnings.warn("Using default SESSION_SECRET. Set SESSION_SECRET in production deployments.", RuntimeWarning)

session_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="fileshare-session")


def _create_session_token(user_id: int) -> str:
    return session_serializer.dumps({"uid": user_id})


def _read_session_token(token: str) -> int | None:
    try:
        data = session_serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid")
    return uid if isinstance(uid, int) else None


def _user_from_cookie(request: Request, db: Session) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    user_id = _read_session_token(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = _user_from_cookie(request, db)
    files = []
    if user:
        files = (
            db.query(StoredFile)
            .filter(StoredFile.owner_id == user.id)
            .order_by(StoredFile.uploaded_at.desc())
            .all()
        )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "user": user,
            "files": files,
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
        },
    )


@app.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip()
    if len(username) < 3 or len(password) < 6:
        return RedirectResponse(url="/?error=Username+or+password+is+too+short", status_code=303)

    if db.query(User).filter(User.username == username).first():
        return RedirectResponse(url="/?error=Username+already+exists", status_code=303)

    user = User(username=username, password_hash=pwd_context.hash(password))
    db.add(user)
    db.commit()
    return RedirectResponse(url="/?message=Registration+successful.+Please+log+in", status_code=303)


@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user or not pwd_context.verify(password, user.password_hash):
        return RedirectResponse(url="/?error=Invalid+credentials", status_code=303)

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _create_session_token(user.id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=SESSION_SECURE,
    )
    return response


@app.post("/logout")
def logout():
    response = RedirectResponse(url="/?message=Logged+out", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.post("/upload")
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = _user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/?error=Please+log+in+first", status_code=303)

    if not file.filename:
        return RedirectResponse(url="/?error=Choose+a+file+to+upload", status_code=303)

    safe_name = Path(file.filename).name.replace("/", "_").replace("\\", "_").replace("..", "_")
    storage_name = f"{uuid4().hex}_{safe_name}"
    destination = UPLOAD_DIR / storage_name

    size = 0
    with destination.open("wb") as output:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                output.close()
                destination.unlink(missing_ok=True)
                return RedirectResponse(url="/?error=File+is+too+large", status_code=303)
            output.write(chunk)
    stored = StoredFile(
        owner_id=user.id,
        original_name=Path(file.filename).name,
        storage_name=storage_name,
        content_type=file.content_type,
        size_bytes=size,
    )
    db.add(stored)
    db.commit()

    return RedirectResponse(url="/?message=File+uploaded", status_code=303)


@app.get("/download/{file_id}")
def download_file(file_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    stored = db.query(StoredFile).filter(StoredFile.id == file_id, StoredFile.owner_id == user.id).first()
    if not stored:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = UPLOAD_DIR / stored.storage_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file missing")

    return FileResponse(path=file_path, filename=stored.original_name, media_type=stored.content_type)


@app.get("/health")
def health():
    return {"status": "ok", "environment": os.getenv("APP_ENV", "local")}
