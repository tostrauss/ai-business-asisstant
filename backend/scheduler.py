# backend/scheduler.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import SessionLocal
from models import Appointment, Client
from websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)

class AppointmentScheduler:
    """
    Scheduler for automated tasks:
    - Send appointment reminders
    - Check for upcoming appointments
    - Clean up old data
    - Generate reports
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        self.scheduler = AsyncIOScheduler()
        self.connection_manager = connection_manager
        self.is_running = False
        
    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        # Schedule tasks
        self._schedule_tasks()
        
        # Start scheduler
        self.scheduler.start()
        self.is_running = True
        logger.info("Scheduler started successfully")
    
    def shutdown(self):
        """Shutdown the scheduler"""
        if not self.is_running:
            return
        
        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Scheduler shut down")
    
    def _schedule_tasks(self):
        """Schedule all periodic tasks"""
        
        # Send reminders every hour
        self.scheduler.add_job(
            self.send_appointment_reminders,
            trigger=CronTrigger(minute=0),  # Every hour at :00
            id='send_reminders',
            name='Send Appointment Reminders',
            replace_existing=True
        )
        
        # Check upcoming appointments every 15 minutes
        self.scheduler.add_job(
            self.check_upcoming_appointments,
            trigger=CronTrigger(minute='*/15'),  # Every 15 minutes
            id='check_upcoming',
            name='Check Upcoming Appointments',
            replace_existing=True
        )
        
        # Daily cleanup at 2 AM
        self.scheduler.add_job(
            self.daily_cleanup,
            trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM daily
            id='daily_cleanup',
            name='Daily Cleanup',
            replace_existing=True
        )
        
        # Weekly report on Monday at 9 AM
        self.scheduler.add_job(
            self.generate_weekly_report,
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='weekly_report',
            name='Generate Weekly Report',
            replace_existing=True
        )
        
        logger.info("Scheduled tasks configured")
    
    async def send_appointment_reminders(self):
        """
        Send reminders for appointments happening in the next 24 hours
        """
        logger.info("Running: Send appointment reminders")
        
        db = SessionLocal()
        try:
            # Get current time and 24 hours from now
            now = datetime.utcnow()
            tomorrow = now + timedelta(hours=24)
            
            # Find appointments that need reminders
            appointments = db.query(Appointment).filter(
                Appointment.status == "confirmed",
                Appointment.reminder_sent == False,
                Appointment.scheduled_date >= now,
                Appointment.scheduled_date <= tomorrow
            ).all()
            
            reminder_count = 0
            for appointment in appointments:
                try:
                    # Create reminder message
                    time_until = appointment.scheduled_date - now
                    hours_until = int(time_until.total_seconds() / 3600)
                    
                    reminder_message = f"""
🔔 Appointment Reminder

You have an upcoming appointment:
• Service: {appointment.service_type}
• Date: {appointment.scheduled_date.strftime('%A, %B %d, %Y')}
• Time: {appointment.scheduled_date.strftime('%I:%M %p')}
• Duration: {appointment.duration_minutes} minutes

This appointment is in {hours_until} hours.

If you need to reschedule or cancel, please let me know as soon as possible.
                    """.strip()
                    
                    # Send via WebSocket if client is connected
                    await self.connection_manager.send_personal_message(
                        reminder_message,
                        appointment.client_id
                    )
                    
                    # Mark reminder as sent
                    appointment.reminder_sent = True
                    reminder_count += 1
                    
                    logger.info(f"Sent reminder for appointment {appointment.id}")
                    
                except Exception as e:
                    logger.error(f"Error sending reminder for appointment {appointment.id}: {e}")
            
            db.commit()
            logger.info(f"Sent {reminder_count} appointment reminders")
            
        except Exception as e:
            logger.error(f"Error in send_appointment_reminders: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def check_upcoming_appointments(self):
        """
        Check for appointments starting soon and send notifications
        """
        logger.info("Running: Check upcoming appointments")
        
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            soon = now + timedelta(minutes=30)  # Next 30 minutes
            
            appointments = db.query(Appointment).filter(
                Appointment.status == "confirmed",
                Appointment.scheduled_date >= now,
                Appointment.scheduled_date <= soon
            ).all()
            
            for appointment in appointments:
                try:
                    minutes_until = int((appointment.scheduled_date - now).total_seconds() / 60)
                    
                    if minutes_until <= 15:
                        message = f"⏰ Your appointment starts in {minutes_until} minutes!"
                    else:
                        message = f"📅 Reminder: Your appointment starts in {minutes_until} minutes"
                    
                    await self.connection_manager.send_personal_message(
                        message,
                        appointment.client_id
                    )
                    
                except Exception as e:
                    logger.error(f"Error notifying about appointment {appointment.id}: {e}")
            
        except Exception as e:
            logger.error(f"Error in check_upcoming_appointments: {e}")
        finally:
            db.close()
    
    async def daily_cleanup(self):
        """
        Daily cleanup tasks:
        - Mark past appointments as completed if not already done
        - Clean up old conversation data
        - Update statistics
        """
        logger.info("Running: Daily cleanup")
        
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            
            # Mark past confirmed appointments as completed
            past_appointments = db.query(Appointment).filter(
                Appointment.status == "confirmed",
                Appointment.scheduled_date < now - timedelta(hours=1)
            ).all()
            
            completed_count = 0
            for appointment in past_appointments:
                appointment.status = "completed"
                completed_count += 1
            
            db.commit()
            logger.info(f"Marked {completed_count} past appointments as completed")
            
            # Reset reminder_sent flag for rescheduled appointments
            rescheduled = db.query(Appointment).filter(
                Appointment.reminder_sent == True,
                Appointment.scheduled_date > now
            ).all()
            
            for appointment in rescheduled:
                appointment.reminder_sent = False
            
            db.commit()
            
            logger.info("Daily cleanup completed successfully")
            
        except Exception as e:
            logger.error(f"Error in daily_cleanup: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def generate_weekly_report(self):
        """
        Generate weekly statistics report
        """
        logger.info("Running: Generate weekly report")
        
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            week_ago = now - timedelta(days=7)
            
            # Count appointments by status
            total = db.query(Appointment).filter(
                Appointment.created_at >= week_ago
            ).count()
            
            confirmed = db.query(Appointment).filter(
                Appointment.created_at >= week_ago,
                Appointment.status == "confirmed"
            ).count()
            
            completed = db.query(Appointment).filter(
                Appointment.created_at >= week_ago,
                Appointment.status == "completed"
            ).count()
            
            cancelled = db.query(Appointment).filter(
                Appointment.created_at >= week_ago,
                Appointment.status == "cancelled"
            ).count()
            
            # New clients
            new_clients = db.query(Client).filter(
                Client.created_at >= week_ago
            ).count()
            
            report = f"""
📊 Weekly Report - {week_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}

Appointments:
• Total created: {total}
• Confirmed: {confirmed}
• Completed: {completed}
• Cancelled: {cancelled}

Clients:
• New clients: {new_clients}

Performance:
• Completion rate: {(completed/total*100 if total > 0 else 0):.1f}%
• Cancellation rate: {(cancelled/total*100 if total > 0 else 0):.1f}%
            """.strip()
            
            logger.info(f"Weekly Report:\n{report}")
            
            # Optionally send to admin or save to file
            # TODO: Send email to admin
            
        except Exception as e:
            logger.error(f"Error in generate_weekly_report: {e}")
        finally:
            db.close()
    
    async def send_proactive_outreach(self):
        """
        Send proactive outreach to clients who haven't scheduled recently
        """
        logger.info("Running: Proactive outreach")
        
        db = SessionLocal()
        try:
            # Find clients with last appointment > 30 days ago
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            clients = db.query(Client).filter(
                Client.last_appointment_date < thirty_days_ago
            ).all()
            
            outreach_message = """
👋 Hi! It's been a while since your last appointment.

We'd love to see you again! Would you like to schedule a follow-up appointment?

Let me know if you have any questions or if there's anything I can help you with.
            """.strip()
            
            sent_count = 0
            for client in clients:
                try:
                    await self.connection_manager.send_personal_message(
                        outreach_message,
                        client.id
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending outreach to client {client.id}: {e}")
            
            logger.info(f"Sent proactive outreach to {sent_count} clients")
            
        except Exception as e:
            logger.error(f"Error in send_proactive_outreach: {e}")
        finally:
            db.close()
    
    def get_scheduled_jobs(self) -> List[dict]:
        """Get list of scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs