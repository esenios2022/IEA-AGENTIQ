from pydantic import BaseModel, EmailStr


class LeadCreate(BaseModel):
    nombre: str
    email: EmailStr
    empresa: str | None = None


class LeadOut(LeadCreate):
    id: int

    model_config = {"from_attributes": True}
