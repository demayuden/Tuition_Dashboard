from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas, models, crud
from ..db import get_db

router = APIRouter(prefix="/packages", tags=["Packages"])


# --------------------------------------------------------
# GET ONE PACKAGE
# --------------------------------------------------------
@router.get("/{package_id}", response_model=schemas.PackageOut)
def get_package(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


# --------------------------------------------------------
# TOGGLE PAYMENT STATUS
# --------------------------------------------------------
@router.post("/{package_id}/payment")
def toggle_payment_status(package_id: int, paid: bool, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    updated = crud.toggle_payment(db, pkg, paid)
    return {
        "status": "ok",
        "package_id": updated.id,
        "payment_status": updated.payment_status
    }


# --------------------------------------------------------
# REGENERATE LESSON DATES (skip closures, recalc)
# --------------------------------------------------------
@router.post("/{package_id}/regenerate")
def regenerate_package(package_id: int, db: Session = Depends(get_db)):
    pkg = crud.get_package(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    crud.regenerate_package(db, pkg)

    return {
        "status": "ok",
        "message": "Lessons regenerated successfully",
        "package_id": pkg.id
    }
