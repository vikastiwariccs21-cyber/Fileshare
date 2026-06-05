# Fileshare (LAN + Air-gapped Friendly)

This repository now includes a minimal end-to-end private-network file sharing system using:

- **FastAPI** (backend API + server-rendered pages)
- **HTML/CSS/JavaScript** (modern themed UI)
- **SQL database support** (SQLite by default, MySQL/XAMPP ready)

## Features

- User registration and login
- Authenticated file upload
- Per-user file listing and download
- LAN deployment support (`0.0.0.0` bind)
- MySQL schema for XAMPP in [`/sql/schema.sql`](/sql/schema.sql)

## Project structure

- `/app/main.py` - FastAPI app and routes
- `/app/models.py` - SQLAlchemy models
- `/app/database.py` - DB session and engine setup
- `/app/templates/index.html` - UI
- `/app/static/style.css` - modern theme
- `/app/static/app.js` - tiny client-side UX helper
- `/sql/schema.sql` - XAMPP/MySQL schema
- `/tests/test_app.py` - focused flow test

## Run in VS Code

1. Open this folder in VS Code.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run app (default SQLite):

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

5. Open from LAN: `http://<server-ip>:8000`

Set security-related environment variables for deployment:

```bash
export SESSION_SECRET="replace-with-a-random-secret"
export SESSION_SECURE=false   # true when HTTPS is enabled
export MAX_UPLOAD_BYTES=52428800
```

## MySQL with XAMPP

1. Start Apache + MySQL in XAMPP.
2. Run SQL from `/sql/schema.sql` in phpMyAdmin.
3. Set DB URL and run server:

   ```bash
   export DATABASE_URL='mysql+pymysql://root:<password>@127.0.0.1:3306/fileshare_lan'
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## Run tests

```bash
pytest -q
```
