from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_id: int
    start_time: datetime

class AppointmentCancel(BaseModel):
    reason: str = Field(..., min_length=3)

class AppointmentReschedule(BaseModel):
    new_start_time: datetime

class AppointmentResponse(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    start_time: datetime
    end_time: datetime
    status: str
    cancellation_reason: Optional[str] = None

    class Config:
        from_attributes = True