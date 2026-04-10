from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from db.connection import get_db
from datetime import datetime, timedelta
from services.email_service import log_notification

scheduler = AsyncIOScheduler()


async def auto_cancel_pending_bookings():
    """Cancel bookings stuck in 'pending' for more than 15 minutes"""
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    
    result = await db.bookings.update_many(
        {"status": "pending", "created_at": {"$lt": cutoff}},
        {
            "$set": {
                "status": "cancelled", 
                "cancellation_reason": "auto_expired",
                "updated_at": datetime.utcnow()
            },
            "$push": {
                "status_history": {
                    "status": "cancelled", 
                    "changed_at": datetime.utcnow(), 
                    "changed_by": "system"
                }
            }
        }
    )
    
    if result.modified_count > 0:
        print(f"[Scheduler] Auto-cancelled {result.modified_count} pending bookings")


async def mark_completed_bookings():
    """Mark past confirmed bookings as completed"""
    db = get_db()
    
    result = await db.bookings.update_many(
        {"status": "confirmed", "end_datetime": {"$lt": datetime.utcnow()}},
        {
            "$set": {"status": "completed", "updated_at": datetime.utcnow()},
            "$push": {
                "status_history": {
                    "status": "completed", 
                    "changed_at": datetime.utcnow(), 
                    "changed_by": "system"
                }
            }
        }
    )
    
    if result.modified_count > 0:
        print(f"[Scheduler] Marked {result.modified_count} bookings as completed")


async def cleanup_abandoned_sessions():
    """Mark old active chat sessions as abandoned"""
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(hours=24)
    
    result = await db.chat_sessions.update_many(
        {"status": "active", "last_message_at": {"$lt": cutoff}},
        {"$set": {"status": "abandoned"}}
    )
    
    if result.modified_count > 0:
        print(f"[Scheduler] Marked {result.modified_count} sessions as abandoned")


async def cleanup_old_notifications():
    """Archive/delete old notification log entries (older than 90 days)"""
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(days=90)
    
    result = await db.notifications_log.delete_many(
        {"created_at": {"$lt": cutoff}}
    )
    
    if result.deleted_count > 0:
        print(f"[Scheduler] Cleaned up {result.deleted_count} old notification logs")


async def mark_no_show_bookings():
    """Mark confirmed bookings that have passed as no-show"""
    db = get_db()
    
    # Bookings that ended more than 1 hour ago and still confirmed
    cutoff = datetime.utcnow() - timedelta(hours=1)
    
    result = await db.bookings.update_many(
        {"status": "confirmed", "end_datetime": {"$lt": cutoff}},
        {
            "$set": {"status": "no_show", "updated_at": datetime.utcnow()},
            "$push": {
                "status_history": {
                    "status": "no_show", 
                    "changed_at": datetime.utcnow(), 
                    "changed_by": "system"
                }
            }
        }
    )
    
    if result.modified_count > 0:
        print(f"[Scheduler] Marked {result.modified_count} bookings as no-show")


def start_scheduler():
    """Start all background jobs"""
    # Auto-cancel pending bookings every 5 minutes
    scheduler.add_job(
        auto_cancel_pending_bookings,
        trigger=IntervalTrigger(minutes=5),
        id="auto_cancel_pending",
        replace_existing=True
    )
    
    # Mark completed bookings every 10 minutes
    scheduler.add_job(
        mark_completed_bookings,
        trigger=IntervalTrigger(minutes=10),
        id="mark_completed",
        replace_existing=True
    )
    
    # Cleanup abandoned sessions every 6 hours
    scheduler.add_job(
        cleanup_abandoned_sessions,
        trigger=IntervalTrigger(hours=6),
        id="cleanup_sessions",
        replace_existing=True
    )
    
    # Cleanup old notifications daily
    scheduler.add_job(
        cleanup_old_notifications,
        trigger=IntervalTrigger(days=1),
        id="cleanup_notifications",
        replace_existing=True
    )
    
    # Mark no-shows every hour
    scheduler.add_job(
        mark_no_show_bookings,
        trigger=IntervalTrigger(hours=1),
        id="mark_no_show",
        replace_existing=True
    )
    
    scheduler.start()
    print("[Scheduler] Background jobs started")


def stop_scheduler():
    """Stop all background jobs"""
    scheduler.shutdown()
    print("[Scheduler] Background jobs stopped")
