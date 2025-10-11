# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize connection manager
manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI Business Assistant API...")
    yield
    # Shutdown
    logger.info("Shutting down AI Business Assistant API...")

app = FastAPI(
    title="AI Business Assistant API",
    version="1.0.0",
    description="AI-powered business assistant for scheduling and client communication",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:80"],
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
            
            # Generate AI response (simplified for now)
            response_content = f"I received your message: '{message_data['content']}'. How can I help you schedule an appointment?"
            
            # Save AI response
            ai_message = Message(
                conversation_id=conversation.id,
                content=response_content,
                sender_type="assistant",
                timestamp=datetime.utcnow()
            )
            db.add(ai_message)
            db.commit()
            
            # Send response to client
            await websocket.send_text(json.dumps({
                'type': 'message',
                'content': response_content,
                'timestamp': datetime.utcnow().isoformat()
            }))
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        if conversation:
            conversation.ended_at = datetime.utcnow()
            conversation.status = "ended"
            db.commit()
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"Error in websocket: {e}")
        manager.disconnect(client_id)
    finally:
        db.close()

# REST endpoints
@app.get("/")
async def root():
    return {"message": "AI Business Assistant API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "AI Business Assistant"
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
    db: Session = Depends(get_db)
):
    query = db.query(Appointment)
    if client_id:
        query = query.filter(Appointment.client_id == client_id)
    if status:
        query = query.filter(Appointment.status == status)
    return query.all()

@app.post("/api/appointments", response_model=AppointmentResponse)
async def create_appointment(
    appointment: AppointmentCreate,
    db: Session = Depends(get_db)
):
    db_appointment = Appointment(**appointment.dict())
    db.add(db_appointment)
    db.commit()
    db.refresh(db_appointment)
    
    # Send confirmation via WebSocket if client is connected
    await manager.send_personal_message(
        f"Your appointment has been scheduled for {db_appointment.scheduled_date}",
        appointment.client_id
    )
    
    return db_appointment

@app.get("/api/conversations/{client_id}", response_model=List[ConversationResponse])
async def get_conversations(client_id: str, db: Session = Depends(get_db)):
    conversations = db.query(Conversation).filter(
        Conversation.client_id == client_id
    ).order_by(Conversation.started_at.desc()).all()
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
    # Generate available slots (mock data for now)
    base_date = request.preferred_date.replace(hour=9, minute=0, second=0, microsecond=0)
    available_slots = []
    
    for i in range(5):
        slot_time = base_date + timedelta(hours=i)
        available_slots.append({
            "time": slot_time.strftime("%I:%M %p"),
            "datetime": slot_time.isoformat(),
            "available": True
        })
    
    return SchedulingResponse(
        available_slots=available_slots,
        ai_suggestions=[
            {"time": available_slots[0]["time"], "reason": "First available slot", "score": 0.9}
        ],
        message=f"I found {len(available_slots)} available times. Would you like to book one?"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)