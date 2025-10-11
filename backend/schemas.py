# backend/schemas.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

# Client schemas
class ClientBase(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class ClientResponse(ClientBase):
    last_appointment_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Appointment schemas
class AppointmentCreate(BaseModel):
    client_id: str
    service_type: str
    scheduled_date: datetime
    duration_minutes: int = 60
    notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: int
    client_id: str
    service_type: str
    scheduled_date: datetime
    duration_minutes: int
    status: str
    notes: Optional[str]
    reminder_sent: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Message schemas
class MessageCreate(BaseModel):
    content: str
    sender_type: str

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    content: str
    sender_type: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

# Conversation schemas
class ConversationResponse(BaseModel):
    id: int
    client_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    initiated_by: str
    summary: Optional[str] = None
    
    class Config:
        from_attributes = True

# Scheduling schemas
class SchedulingRequest(BaseModel):
    client_id: str
    service_type: str
    preferred_date: datetime
    duration_minutes: int = 60
    preferences: Optional[Dict[str, Any]] = None

class SchedulingResponse(BaseModel):
    available_slots: List[Dict[str, Any]]
    ai_suggestions: List[Dict[str, Any]]
    message: str