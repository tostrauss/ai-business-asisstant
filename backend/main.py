# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import json
import asyncio
from contextlib import asynccontextmanager
import logging

from database import get_db, engine, Base
from models import Conversation, Message, Appointment, Client
from schemas import (
    MessageCreate, MessageResponse, ConversationResponse,
    AppointmentCreate, AppointmentResponse, ClientResponse,
    SchedulingRequest, SchedulingResponse
)
from websocket_manager import ConnectionManager
from scheduler import AppointmentScheduler
from ai_service import ai_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize managers
manager = ConnectionManager()
scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI Business Assistant API...")
    global scheduler
    scheduler = AppointmentScheduler(manager)
    scheduler.start()
    yield
    # Shutdown
    logger.info("Shutting down AI Business Assistant API...")
    if scheduler:
        scheduler.shutdown()

app = FastAPI(
    title="AI Business Assistant API",
    version="1.0.0",
    description="AI-powered business assistant for scheduling and client communication",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:80", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket endpoint for real-time chat
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    db = next(get_db())
    
    try:
        # Send welcome message
        await websocket.send_text(json.dumps({
            'type': 'connection',
            'content': 'Connected to AI Business Assistant',
            'timestamp': datetime.utcnow().isoformat()
        }))
        
        # Get or create client
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            client = Client(
                id=client_id,
                name=f"Client {client_id[:8]}",
                email=f"{client_id}@example.com",
                created_at=datetime.utcnow()
            )
            db.add(client)
            db.commit()
            db.refresh(client)
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Create or get conversation
            conversation = db.query(Conversation).filter(
                Conversation.client_id == client_id,
                Conversation.status == "active"
            ).first()
            
            if not conversation:
                conversation = Conversation(
                    client_id=client_id,
                    started_at=datetime.utcnow(),
                    status="active"
                )
                db.add(conversation)
                db.commit()
                db.refresh(conversation)
            
            # Save user message
            user_message = Message(
                conversation_id=conversation.id,
                content=message_data['content'],
                sender_type="client",
                timestamp=datetime.utcnow()
            )
            db.add(user_message)
            db.commit()
            
            # Get conversation history
            recent_messages = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(Message.timestamp.desc()).limit(20).all()
            
            conversation_history = [
                {
                    "content": msg.content,
                    "sender_type": msg.sender_type
                }
                for msg in reversed(recent_messages)
            ]
            
            # Get client context
            client_context = {
                "client_id": client.id,
                "name": client.name,
                "email": client.email,
                "last_appointment": client.last_appointment_date.isoformat() if client.last_appointment_date else None
            }
            
            # Process with AI service
            ai_response = await ai_service.process_message(
                message_data['content'],
                conversation_history,
                client_context
            )
            
            # Save AI response
            ai_message = Message(
                conversation_id=conversation.id,
                content=ai_response['response'],
                sender_type="assistant",
                timestamp=datetime.utcnow(),
                metadata={"intent": ai_response.get('intent'), "actions": ai_response.get('actions')}
            )
            db.add(ai_message)
            db.commit()
            
            # Send response to client
            response_payload = {
                'type': 'message',
                'content': ai_response['response'],
                'timestamp': datetime.utcnow().isoformat(),
                'intent': ai_response.get('intent'),
                'actions': ai_response.get('actions')
            }
            
            await websocket.send_text(json.dumps(response_payload))
            
            # Process any actions
            for action in ai_response.get('actions', []):
                await process_action(action, client_id, conversation.id, db, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        if conversation:
            conversation.ended_at = datetime.utcnow()
            conversation.status = "ended"
            
            # Generate conversation summary
            messages = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).all()
            
            if messages:
                message_list = [{"content": m.content, "sender_type": m.sender_type} for m in messages]
                summary = await ai_service.summarize_conversation(message_list)
                conversation.summary = summary
            
            db.commit()
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"Error in websocket: {e}")
        manager.disconnect(client_id)
    finally:
        db.close()

async def process_action(action: dict, client_id: str, conversation_id: int, db: Session, websocket: WebSocket):
    """Process AI-suggested actions"""
    try:
        action_type = action.get('type')
        data = action.get('data', {})
        
        if action_type == 'show_availability':
            # Send available slots to client
            slots_message = {
                'type': 'available_slots',
                'slots': data.get('suggested_times', []),
                'timestamp': datetime.utcnow().isoformat()
            }
            await websocket.send_text(json.dumps(slots_message))
            
        elif action_type == 'confirm_appointment':
            # Handle appointment confirmation
            logger.info(f"Processing appointment confirmation for {client_id}")
            
        elif action_type == 'modify_appointment':
            # Handle appointment modification
            logger.info(f"Processing appointment modification for {client_id}")
            
    except Exception as e:
        logger.error(f"Error processing action: {e}")

# REST endpoints
@app.get("/")
async def root():
    return {"message": "AI Business Assistant API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    # Check AI service status
    ai_status = "connected" if ai_service.client else "not configured"
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "AI Business Assistant",
        "ai_status": ai_status,
        "scheduler": "running" if scheduler and scheduler.is_running else "stopped"
    }

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics"""
    total_clients = db.query(Client).count()
    total_appointments = db.query(Appointment).count()
    pending_appointments = db.query(Appointment).filter(Appointment.status == "pending").count()
    confirmed_appointments = db.query(Appointment).filter(Appointment.status == "confirmed").count()
    active_conversations = db.query(Conversation).filter(Conversation.status == "active").count()
    
    return {
        "total_clients": total_clients,
        "total_appointments": total_appointments,
        "pending_appointments": pending_appointments,
        "confirmed_appointments": confirmed_appointments,
        "active_conversations": active_conversations,
        "connected_clients": len(manager.active_connections),
        "timestamp": datetime.utcnow()
    }

@app.get("/api/clients/{client_id}", response_model=ClientResponse)
async def get_client(client_id: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        # Create a demo client if not exists
        client = Client(
            id=client_id,
            name="Demo User",
            email=f"{client_id}@example.com",
            created_at=datetime.utcnow()
        )
        db.add(client)
        db.commit()
        db.refresh(client)
    return client

@app.get("/api/appointments", response_model=List[AppointmentResponse])
async def get_appointments(
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Appointment)
    
    if client_id:
        query = query.filter(Appointment.client_id == client_id)
    if status:
        query = query.filter(Appointment.status == status)
    if start_date:
        query = query.filter(Appointment.scheduled_date >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Appointment.scheduled_date <= datetime.fromisoformat(end_date))
    
    return query.order_by(Appointment.scheduled_date.desc()).all()

@app.post("/api/appointments", response_model=AppointmentResponse)
async def create_appointment(
    appointment: AppointmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Create appointment
    db_appointment = Appointment(**appointment.dict())
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    
    # Update client's last appointment date
    client = db.query(Client).filter(Client.id == appointment.client_id).first()
    if client:
        client.last_appointment_date = appointment.scheduled_date
        db.commit()
    
    # Send confirmation via WebSocket if client is connected
    confirmation_message = f"""
✅ Appointment Confirmed!

• Service: {db_appointment.service_type}
• Date: {db_appointment.scheduled_date.strftime('%A, %B %d, %Y')}
• Time: {db_appointment.scheduled_date.strftime('%I:%M %p')}
• Duration: {db_appointment.duration_minutes} minutes

We'll send you a reminder 24 hours before your appointment.
"""
    
    await manager.send_personal_message(
        confirmation_message,
        appointment.client_id
    )
    
    # Schedule reminder task
    background_tasks.add_task(schedule_reminder, db_appointment.id)
    
    return db_appointment

async def schedule_reminder(appointment_id: int):
    """Schedule a reminder for an appointment"""
    logger.info(f"Scheduling reminder for appointment {appointment_id}")
    # This would integrate with the scheduler

@app.patch("/api/appointments/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    status: Optional[str] = None,
    scheduled_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if status:
        appointment.status = status
    if scheduled_date:
        appointment.scheduled_date = datetime.fromisoformat(scheduled_date)
        appointment.reminder_sent = False  # Reset reminder for rescheduled appointments
    
    appointment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(appointment)
    
    return appointment

@app.delete("/api/appointments/{appointment_id}")
async def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appointment.status = "cancelled"
    appointment.updated_at = datetime.utcnow()
    db.commit()
    
    # Notify client
    await manager.send_personal_message(
        f"Your appointment on {appointment.scheduled_date.strftime('%B %d')} has been cancelled.",
        appointment.client_id
    )
    
    return {"message": "Appointment cancelled successfully"}

@app.get("/api/conversations/{client_id}", response_model=List[ConversationResponse])
async def get_conversations(
    client_id: str, 
    limit: int = 10,
    db: Session = Depends(get_db)
):
    conversations = db.query(Conversation).filter(
        Conversation.client_id == client_id
    ).order_by(Conversation.started_at.desc()).limit(limit).all()
    return conversations

@app.get("/api/messages/{conversation_id}", response_model=List[MessageResponse])
async def get_messages(conversation_id: int, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.timestamp).all()
    return messages

@app.post("/api/scheduling/request", response_model=SchedulingResponse)
async def request_scheduling(
    request: SchedulingRequest,
    db: Session = Depends(get_db)
):
    # Get AI service to suggest optimal slots
    available_slots = []
    base_date = request.preferred_date.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Check for existing appointments to avoid conflicts
    existing_appointments = db.query(Appointment).filter(
        Appointment.scheduled_date >= base_date,
        Appointment.scheduled_date < base_date + timedelta(days=7),
        Appointment.status.in_(["confirmed", "pending"])
    ).all()
    
    booked_times = set()
    for appt in existing_appointments:
        booked_times.add(appt.scheduled_date.replace(second=0, microsecond=0))
    
    # Generate available slots
    for day_offset in range(7):
        current_date = base_date + timedelta(days=day_offset)
        
        # Skip weekends
        if current_date.weekday() >= 5:
            continue
        
        # Generate hourly slots from 9 AM to 5 PM
        for hour in range(9, 17):
            slot_time = current_date.replace(hour=hour)
            
            if slot_time not in booked_times and slot_time > datetime.utcnow():
                available_slots.append({
                    "datetime": slot_time.isoformat(),
                    "time": slot_time.strftime("%I:%M %p"),
                    "available": True
                })
    
    # AI suggestions for best times
    ai_suggestions = []
    if available_slots:
        # Prefer morning slots
        morning_slots = [s for s in available_slots[:3]]
        for idx, slot in enumerate(morning_slots):
            ai_suggestions.append({
                "time": slot["time"],
                "datetime": slot["datetime"],
                "reason": "Morning appointment - less waiting time",
                "score": 0.9 - (idx * 0.1)
            })
    
    return SchedulingResponse(
        available_slots=available_slots[:10],  # Return top 10 slots
        ai_suggestions=ai_suggestions[:3],     # Top 3 suggestions
        message=f"I found {len(available_slots)} available times. Would you like to book one?"
    )

@app.get("/api/scheduler/jobs")
async def get_scheduler_jobs():
    """Get scheduled job information"""
    if not scheduler:
        return {"message": "Scheduler not running"}
    
    return {
        "status": "running" if scheduler.is_running else "stopped",
        "jobs": scheduler.get_scheduled_jobs()
    }

@app.post("/api/outreach/{client_id}")
async def send_outreach(
    client_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Send proactive outreach to a client"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Generate follow-up message
    client_history = {
        "last_appointment_date": client.last_appointment_date.isoformat() if client.last_appointment_date else None
    }
    
    follow_up = await ai_service.suggest_follow_up(client_history)
    
    if follow_up:
        # Send via WebSocket if connected
        await manager.send_personal_message(follow_up, client_id)
        
        # Create conversation record
        conversation = Conversation(
            client_id=client_id,
            started_at=datetime.utcnow(),
            status="outreach",
            initiated_by="system"
        )
        db.add(conversation)
        
        # Save outreach message
        message = Message(
            conversation_id=conversation.id,
            content=follow_up,
            sender_type="assistant",
            timestamp=datetime.utcnow()
        )
        db.add(message)
        db.commit()
        
        return {"message": "Outreach sent successfully", "content": follow_up}
    
    return {"message": "No outreach needed at this time"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)