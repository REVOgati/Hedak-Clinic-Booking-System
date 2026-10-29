from fastapi import FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app import models, schemas, crud

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Clinic Booking API", version="1.0.0")

@app.post("/appointments", response_model=schemas.AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(payload: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    return crud.book_appointment(db, payload)

@app.get("/doctors/{id}/availability")
def get_availability(id: int, date: str = Query(..., description="Format: YYYY-MM-DD"), db: Session = Depends(get_db)):
    return {"doctor_id": id, "date": date, "available_slots": crud.get_doctor_availability(db, id, date)}

@app.patch("/appointments/{id}/cancel", response_model=schemas.AppointmentResponse)
def cancel_appointment(id: int, payload: schemas.AppointmentCancel, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    if appt.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Appointment is already cancelled.")
    
    appt.status = "CANCELLED"
    appt.cancellation_reason = payload.reason
    db.commit()
    db.refresh(appt)
    return appt

@app.patch("/appointments/{id}/reschedule", response_model=schemas.AppointmentResponse)
def reschedule_appointment(id: int, payload: schemas.AppointmentReschedule, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    if appt.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Cannot reschedule a cancelled appointment.")
    
    # Cancel old slot temporarily and book new
    appt.status = "CANCELLED"
    db.flush()
    
    try:
        new_appt = crud.book_appointment(
            db, 
            schemas.AppointmentCreate(
                doctor_id=appt.doctor_id,
                patient_id=appt.patient_id,
                start_time=payload.new_start_time
            )
        )
        db.commit()
        return new_appt
    except Exception as e:
        db.rollback()
        raise e