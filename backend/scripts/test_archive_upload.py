"""Quick test for release note archive upload."""
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import AsanaProject

client = TestClient(app)

db = SessionLocal()
project = db.query(AsanaProject).first()
db.close()
gid = project.gid if project else None
print("project_gid", gid)

docx = Path("data/release_notes/archive/20260701_120111_hist.docx")
data = docx.read_bytes() if docx.is_file() else b"PK\x03\x04fake"

files = {"file": (docx.name, BytesIO(data), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
url = f"/api/v1/release-notes/archive?release_date=2026-06-20&title=Test+Upload"
if gid:
    url += f"&project_gid={gid}"

r = client.post(url, files=files)
print("status", r.status_code)
print("body", r.text[:500])
