from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models, schemas
from pydantic import BaseModel
from datetime import date

router = APIRouter(prefix="/closures", tags=["Closures"])

class ClosureIn(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = None
    type: str | None = None

@router.post("/", response_model=ClosureIn)
def create_closure(payload: ClosureIn, db: Session = Depends(get_db)):
    c = models.Closure(start_date=payload.start_date, end_date=payload.end_date,
                       reason=payload.reason, type=payload.type)
    db.add(c); db.commit(); db.refresh(c)
    return c

@router.get("/", response_model=list[ClosureIn])
def list_closures(db: Session = Depends(get_db)):
    return db.query(models.Closure).order_by(models.Closure.start_date).all()

@router.delete("/{closure_id}")
def delete_closure(closure_id:int, db:Session=Depends(get_db)):
    c = db.query(models.Closure).filter(models.Closure.id == closure_id).first()
    if not c: raise HTTPException(404,"Closure not found")
    db.delete(c); db.commit()
    return {"status":"ok"}
