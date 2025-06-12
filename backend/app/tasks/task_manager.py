"""
任务管理器
统一管理所有Celery任务和定时任务配置
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from backend.app.tasks.base_wallet_finder_tasks import BaseWalletFinderTask
from backend.app.core.config import settings
from backend.app.tasks.hot_token_finder_tasks import HotTokenFinder
from backend.app.tasks.smw_daily_process import SMWQueueDailyProcessTask
from backend.app.utils.log_utils import setup_logging


class TaskManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
        self.hot_token_finder = HotTokenFinder()
        self.base_wallet_finder = BaseWalletFinderTask()

        self._setup_scheduled_tasks()
    
    def _setup_scheduled_tasks(self):
        self.scheduler.add_job(
            func=self.find_daily_token_task,
            trigger=IntervalTrigger(minutes=settings.find_daily_token_interval_minutes),
            id='find_daily_token_task',
            name='Find Daily Token Task',
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc)
        )
        logging.info(f"Scheduled task 'find_daily_token_task' to run every {settings.find_daily_token_interval_minutes} minutes")

        self.scheduler.add_job(
            func=self.find_daily_smw_task,
            trigger=CronTrigger(hour=4, minute=0, second=0, timezone='UTC'
            ),
            id='find_daily_smw_task',
            name='Find Daily Smart Wallet Task',
            replace_existing=True,
        )
        logging.info(f"Scheduled task 'find_daily_wallet_task' to run every 24 hours")


    def find_daily_token_task(self):
        self.hot_token_finder.run_scan_cycle()

    def find_daily_smw_task(self):
        SMWQueueDailyProcessTask.process_daily_smw()


    def start_scheduler(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logging.info("Task scheduler started")
    
    def stop_scheduler(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logging.info("Task scheduler stopped")
    
    def get_scheduler_info(self) -> Dict[str, Any]:
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'trigger': str(job.trigger),
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
            })
        
        return {
            'running': self.scheduler.running,
            'timezone': str(self.scheduler.timezone),
            'jobs': jobs
        }


async def main():
    setup_logging()
    logging.info("Starting TaskManager main function...")
    task_manager_instance = TaskManager()
    task_manager_instance.start_scheduler()
    
    # 打印调度器信息
    scheduler_info = task_manager_instance.get_scheduler_info()
    logging.info(f"Scheduler info: {scheduler_info}")
    
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, shutting down...")
        task_manager_instance.stop_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
