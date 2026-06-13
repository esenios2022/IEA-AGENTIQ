from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

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
