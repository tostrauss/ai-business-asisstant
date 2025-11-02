# backend/ai_service.py
from openai import OpenAI
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AIService:
    """
    AI Service for handling OpenAI integration and intelligent responses
    """
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not found. AI features will be limited.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)
        
        self.system_prompt = """
You are an AI Business Assistant specialized in scheduling appointments and managing client communications.
Your responsibilities include:
1. Scheduling and confirming appointments
2. Sending reminders and follow-ups
3. Answering questions about services
4. Providing business hours and availability
5. Being professional, friendly, and helpful

When scheduling appointments:
- Always confirm the date, time, and service type
- Check for conflicts with existing appointments
- Suggest alternative times if requested time is unavailable
- Send confirmation once appointment is booked

Keep responses concise and action-oriented.
"""

    async def process_message(
        self, 
        message: str, 
        conversation_history: List[Dict[str, str]] = None,
        client_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Process a message and generate an AI response
        
        Args:
            message: The user's message
            conversation_history: Previous messages in the conversation
            client_context: Additional context about the client
            
        Returns:
            Dictionary containing response and any actions to take
        """
        if not self.client:
            # Fallback response when OpenAI is not configured
            return self._generate_fallback_response(message)
        
        try:
            # Build conversation context
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add client context if available
            if client_context:
                context_msg = f"Client Information: {json.dumps(client_context)}"
                messages.append({"role": "system", "content": context_msg})
            
            # Add conversation history
            if conversation_history:
                for hist in conversation_history[-10:]:  # Last 10 messages
                    role = "user" if hist.get("sender_type") == "client" else "assistant"
                    messages.append({"role": role, "content": hist.get("content", "")})
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Get AI response
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            ai_response = response.choices[0].message.content
            
            # Analyze intent and extract actions
            intent = await self._analyze_intent(message, ai_response)
            
            return {
                "response": ai_response,
                "intent": intent,
                "actions": self._extract_actions(intent, message, ai_response)
            }
            
        except Exception as e:
            logger.error(f"Error processing AI message: {e}")
            return self._generate_fallback_response(message)
    
    async def _analyze_intent(self, message: str, response: str) -> str:
        """
        Analyze the intent of the message
        """
        message_lower = message.lower()
        
        # Simple intent detection (can be enhanced with AI)
        if any(word in message_lower for word in ["schedule", "book", "appointment", "available"]):
            return "scheduling"
        elif any(word in message_lower for word in ["cancel", "reschedule", "change"]):
            return "modification"
        elif any(word in message_lower for word in ["confirm", "confirmation", "yes", "agree"]):
            return "confirmation"
        elif any(word in message_lower for word in ["remind", "reminder", "forget"]):
            return "reminder"
        elif any(word in message_lower for word in ["price", "cost", "fee", "charge"]):
            return "pricing"
        elif any(word in message_lower for word in ["hour", "open", "close", "when"]):
            return "hours"
        else:
            return "general"
    
    def _extract_actions(self, intent: str, message: str, response: str) -> List[Dict[str, Any]]:
        """
        Extract actionable items from the intent and message
        """
        actions = []
        
        if intent == "scheduling":
            # Extract date/time mentions (simplified - could use NLP)
            actions.append({
                "type": "show_availability",
                "data": {
                    "suggested_times": self._generate_available_slots()
                }
            })
        elif intent == "confirmation":
            actions.append({
                "type": "confirm_appointment",
                "data": {}
            })
        elif intent == "modification":
            actions.append({
                "type": "modify_appointment",
                "data": {}
            })
        
        return actions
    
    def _generate_available_slots(self) -> List[Dict[str, str]]:
        """
        Generate available appointment slots
        """
        slots = []
        base_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Generate slots for the next 5 days
        for day in range(1, 6):
            date = base_time + timedelta(days=day)
            
            # Morning and afternoon slots
            for hour in [9, 10, 11, 14, 15, 16]:
                slot_time = date.replace(hour=hour)
                slots.append({
                    "datetime": slot_time.isoformat(),
                    "display": slot_time.strftime("%A, %B %d at %I:%M %p"),
                    "available": True
                })
        
        return slots[:8]  # Return first 8 slots
    
    def _generate_fallback_response(self, message: str) -> Dict[str, Any]:
        """
        Generate a fallback response when AI is not available
        """
        message_lower = message.lower()
        
        # Basic keyword-based responses
        if "schedule" in message_lower or "appointment" in message_lower:
            response = "I can help you schedule an appointment. What service are you interested in, and when would you prefer?"
            intent = "scheduling"
        elif "cancel" in message_lower:
            response = "I can help you cancel your appointment. Could you provide your appointment details?"
            intent = "modification"
        elif "hour" in message_lower or "open" in message_lower:
            response = "Our business hours are Monday-Friday 9:00 AM - 6:00 PM, and Saturday 10:00 AM - 4:00 PM. We're closed on Sundays."
            intent = "hours"
        elif "price" in message_lower or "cost" in message_lower:
            response = "Our pricing varies by service. Could you tell me which service you're interested in?"
            intent = "pricing"
        else:
            response = "I'm here to help with scheduling appointments and answering questions about our services. How can I assist you today?"
            intent = "general"
        
        return {
            "response": response,
            "intent": intent,
            "actions": []
        }
    
    async def generate_reminder_message(
        self, 
        appointment: Dict[str, Any], 
        reminder_type: str = "24_hour"
    ) -> str:
        """
        Generate a reminder message for an appointment
        """
        if not self.client:
            return self._generate_fallback_reminder(appointment, reminder_type)
        
        try:
            prompt = f"""
Generate a friendly reminder message for an appointment.
Appointment details:
- Service: {appointment.get('service_type')}
- Date: {appointment.get('scheduled_date')}
- Duration: {appointment.get('duration_minutes')} minutes
- Reminder type: {reminder_type}

Keep it professional, friendly, and include all important details.
"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a friendly business assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating reminder: {e}")
            return self._generate_fallback_reminder(appointment, reminder_type)
    
    def _generate_fallback_reminder(
        self, 
        appointment: Dict[str, Any], 
        reminder_type: str
    ) -> str:
        """
        Generate a fallback reminder message
        """
        date = datetime.fromisoformat(appointment.get('scheduled_date', ''))
        formatted_date = date.strftime("%A, %B %d at %I:%M %p")
        
        if reminder_type == "24_hour":
            return f"""
🔔 Appointment Reminder

You have an appointment tomorrow:
• Service: {appointment.get('service_type')}
• Date & Time: {formatted_date}
• Duration: {appointment.get('duration_minutes')} minutes

Please let us know if you need to reschedule or cancel.
Looking forward to seeing you!
"""
        elif reminder_type == "1_hour":
            return f"""
⏰ Your appointment is starting soon!

• Service: {appointment.get('service_type')}
• Time: {date.strftime("%I:%M %p")}

See you soon!
"""
        else:
            return f"Reminder: You have an appointment on {formatted_date}"
    
    async def summarize_conversation(
        self, 
        messages: List[Dict[str, str]]
    ) -> str:
        """
        Generate a summary of a conversation
        """
        if not self.client:
            return "Conversation summary not available."
        
        try:
            # Prepare conversation text
            conversation = "\n".join([
                f"{msg.get('sender_type', 'Unknown')}: {msg.get('content', '')}"
                for msg in messages
            ])
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Summarize this conversation in 2-3 sentences."},
                    {"role": "user", "content": conversation}
                ],
                temperature=0.5,
                max_tokens=100
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error summarizing conversation: {e}")
            return "Conversation summary not available."
    
    async def suggest_follow_up(
        self, 
        client_history: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate follow-up suggestions based on client history
        """
        if not client_history.get("last_appointment_date"):
            return "Would you like to schedule your first appointment with us?"
        
        last_appointment = datetime.fromisoformat(client_history["last_appointment_date"])
        days_since = (datetime.now() - last_appointment).days
        
        if days_since > 90:
            return "It's been a while since your last visit! Would you like to schedule a follow-up appointment?"
        elif days_since > 30:
            return "Time for your regular check-in? Let me know if you'd like to schedule your next appointment."
        
        return None

# Singleton instance
ai_service = AIService()