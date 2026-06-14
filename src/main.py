import csv
import io
from contextlib import asynccontextmanager
from datetime import datetime
from secrets import compare_digest

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.config import settings
from src.database import Base, engine, get_db
from src.models import Lead
from src.schemas import LeadCreate, LeadOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="IEA-AGENTIQ", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    valid_user = compare_digest(credentials.username, settings.admin_user)
    valid_password = compare_digest(credentials.password, settings.admin_password)
    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/leads", response_model=LeadOut)
def create_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    db_lead = Lead(nombre=lead.nombre, email=lead.email, empresa=lead.empresa)
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead


def _leads_query(q: str | None):
    stmt = select(Lead).order_by(Lead.created_at.desc())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Lead.nombre.ilike(like),
                Lead.email.ilike(like),
                Lead.empresa.ilike(like),
            )
        )
    return stmt


@app.get("/admin/leads")
def list_leads(
    request: Request,
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    leads = db.scalars(_leads_query(q)).all()
    return templates.TemplateResponse(
        request,
        "admin_leads.html",
        {"leads": leads, "q": q or "", "total": len(leads)},
    )


@app.get("/admin/leads/export")
def export_leads(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    leads = db.scalars(_leads_query(q)).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "nombre", "email", "empresa", "created_at"])
    for lead in leads:
        writer.writerow(
            [
                lead.id,
                lead.nombre,
                lead.email,
                lead.empresa or "",
                lead.created_at.isoformat(),
            ]
        )
    buffer.seek(0)

    filename = f"leads_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
