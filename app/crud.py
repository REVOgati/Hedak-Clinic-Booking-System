from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app import models, schemas

SLOT_DURATION_MINUTES = 30

def get_doctor_availability(db: Session, doctor_id: int, date_str: str):
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    day_of_week = target_date.weekday()
    
    wh = db.execute(
        select(models.WorkingHours).where(
            models.WorkingHours.doctor_id == doctor_id,
            models.WorkingHours.day_of_week == day_of_week
        )
    .scalars().first()
    
    if not wh:
        return []
    
    start_dt = datetime.strptime(f"{date_str} {wh.start_time}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{date_str} {wh.end_time}", "%Y-%m-%d %H:%M")
    
    # Generate all 30-min slots
    slots = []
    curr = start_dt
    while curr + timedelta(minutes=SLOT_DURATION_MINUTES) <= end_dt:
        slots.append(curr)
        curr += timedelta(minutes=SLOT_DURATION_MINUTES)
        
    # Get active bookings
    bookings = db.execute(
        select(models.Appointment).where(
            models.Appointment.doctor_id == doctor_id,
            models.Appointment.status == "BOOKED",
            models.Appointment.start_time >= start_dt,
            models.Appointment.start_time < end_dt
        )
    ).scalars().all()
    
    booked_times = {b.start_time for b in bookings}
    
    # Filter available slots
    available = [s.strftime("%Y-%m-%d %H:%M") for s in slots if s not in booked_times]
    return available

def book_appointment(db: Session, payload: schemas.AppointmentCreate):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # Bonus rule: Prevent booking within 1 hour of now
    if payload.start_time <= now + timedelta(hours=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bookings must be made at least 1 hour in advance."
        )
        
    if payload.start_time.minute not in (0, 30):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointments must start on the hour or half-hour."
        )

    end_time = payload.start_time + timedelta(minutes=SLOT_DURATION_MINUTES)
    
    # Use database transaction & row locking to prevent race conditions / double booking
    with db.begin():
        # Check overlapping active bookings with lock
        existing = db.execute(
            select(models.Appointment).where(
                models.Appointment.doctor_id == payload.doctor_id,
                models.Appointment.status == "BOOKED",
                models.Appointment.start_time == payload.start_time
            ).with_for_update()
        ).scalars().first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This time slot is already booked."
            )
            
        appointment = models.Appointment(
            doctor_id=payload.doctor_id,
            patient_id=payload.patient_id,
            start_time=payload.start_time,
            end_time=end_time,
            status="BOOKED"
        )
        db.add(appointment)
        db.flush()
        db.refresh(appointment)
        return appointment