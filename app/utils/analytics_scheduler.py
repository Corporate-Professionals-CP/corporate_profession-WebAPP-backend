"""
Analytics scheduler for running background tasks
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from app.utils.analytics_tasks import run_daily_analytics_tasks, run_weekly_analytics_tasks

logger = logging.getLogger(__name__)


class AnalyticsScheduler:
    """Scheduler for analytics background tasks"""
    
    def __init__(self):
        self.running = False
        self.tasks = []
    
    async def start(self):
        """Start the analytics scheduler"""
        if self.running:
            logger.warning("Analytics scheduler is already running")
            return
        
        self.running = True
        logger.info("Starting analytics scheduler")
        
        # Schedule daily tasks (run at 2 AM)
        daily_task = asyncio.create_task(
            self._schedule_daily_tasks()
        )
        self.tasks.append(daily_task)
        
        # Schedule weekly tasks (run on Sunday at 3 AM)
        weekly_task = asyncio.create_task(
            self._schedule_weekly_tasks()
        )
        self.tasks.append(weekly_task)
    
    async def stop(self):
        """Stop the analytics scheduler"""
        if not self.running:
            return
        
        self.running = False
        logger.info("Stopping analytics scheduler")
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to finish
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
    
    async def _schedule_daily_tasks(self):
        """Schedule daily analytics tasks"""
        while self.running:
            try:
                now = datetime.now()
                target_time = now.replace(hour=2, minute=0, second=0, microsecond=0)
                
                # If it's past 2 AM today, schedule for tomorrow
                if now.time() > time(2, 0):
                    target_time = target_time.replace(day=target_time.day + 1)
                
                # Calculate sleep time
                sleep_seconds = (target_time - now).total_seconds()
                
                if sleep_seconds > 0:
                    logger.info(f"Scheduling daily analytics tasks for {target_time}")
                    await asyncio.sleep(sleep_seconds)
                
                if self.running:
                    logger.info("Running daily analytics tasks")
                    await run_daily_analytics_tasks()
                    logger.info("Daily analytics tasks completed")
                
                # Sleep for 23 hours to avoid running multiple times per day
                await asyncio.sleep(23 * 3600)
                
            except asyncio.CancelledError:
                logger.info("Daily analytics task scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in daily analytics scheduler: {str(e)}")
                # Sleep for 1 hour before retrying
                await asyncio.sleep(3600)
    
    async def _schedule_weekly_tasks(self):
        """Schedule weekly analytics tasks"""
        while self.running:
            try:
                now = datetime.now()
                
                # Calculate next Sunday at 3 AM
                days_until_sunday = (6 - now.weekday()) % 7
                if days_until_sunday == 0 and now.time() > time(3, 0):
                    days_until_sunday = 7
                
                target_time = now.replace(
                    hour=3, minute=0, second=0, microsecond=0
                ) + timedelta(days=days_until_sunday)
                
                # Calculate sleep time
                sleep_seconds = (target_time - now).total_seconds()
                
                if sleep_seconds > 0:
                    logger.info(f"Scheduling weekly analytics tasks for {target_time}")
                    await asyncio.sleep(sleep_seconds)
                
                if self.running:
                    logger.info("Running weekly analytics tasks")
                    await run_weekly_analytics_tasks()
                    logger.info("Weekly analytics tasks completed")
                
                # Sleep for 6 days to avoid running multiple times per week
                await asyncio.sleep(6 * 24 * 3600)
                
            except asyncio.CancelledError:
                logger.info("Weekly analytics task scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in weekly analytics scheduler: {str(e)}")
                # Sleep for 1 hour before retrying
                await asyncio.sleep(3600)


# Global scheduler instance
analytics_scheduler = AnalyticsScheduler()


async def start_analytics_scheduler():
    """Start the analytics scheduler"""
    await analytics_scheduler.start()


async def stop_analytics_scheduler():
    """Stop the analytics scheduler"""
    await analytics_scheduler.stop()


# Manual trigger functions for testing
async def trigger_daily_analytics():
    """Manually trigger daily analytics tasks"""
    logger.info("Manually triggering daily analytics tasks")
    await run_daily_analytics_tasks()


async def trigger_weekly_analytics():
    """Manually trigger weekly analytics tasks"""
    logger.info("Manually triggering weekly analytics tasks")
    await run_weekly_analytics_tasks()
