import asyncio
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict
from config import settings
from models import TaskStatus
import logging

logger = logging.getLogger(__name__)


class StorageManager:
    def __init__(self):
        self.storage_path = settings.temp_storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.tasks: Dict[str, dict] = {}

    async def start_cleanup_task(self):
        """Background task to clean up old files"""
        while True:
            try:
                await self.cleanup_old_tasks()
                # Run cleanup every hour
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(300)  # Retry in 5 minutes on error

    async def cleanup_old_tasks(self):
        """Remove tasks older than TTL"""
        cutoff_time = datetime.now() - timedelta(hours=settings.ttl_hours)
        tasks_to_remove = []

        for task_id, task_info in self.tasks.items():
            if task_info.get("created_at", datetime.now()) < cutoff_time:
                tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            await self.delete_task(task_id)

        logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")

    async def create_task(self, task_id: str) -> Path:
        """Create directory structure for a task"""
        task_path = self.storage_path / task_id
        task_path.mkdir(parents=True, exist_ok=True)
        images_path = task_path / "images"
        images_path.mkdir(exist_ok=True)

        self.tasks[task_id] = {
            "status": TaskStatus.PENDING,
            "created_at": datetime.now(),
            "path": task_path,
        }

        return task_path

    async def update_task_status(self, task_id: str, status: TaskStatus, error: str = None):
        """Update task status"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            if error:
                self.tasks[task_id]["error"] = error

    def get_task_status(self, task_id: str) -> dict:
        """Get task status"""
        return self.tasks.get(task_id)

    def get_task_path(self, task_id: str) -> Path:
        """Get task directory path"""
        return self.storage_path / task_id

    def get_zip_path(self, task_id: str) -> Path:
        """Get path to zipped result"""
        return self.storage_path / f"{task_id}.zip"

    async def delete_task(self, task_id: str):
        """Delete task directory and zip file"""
        task_path = self.get_task_path(task_id)
        zip_path = self.get_zip_path(task_id)

        if task_path.exists():
            shutil.rmtree(task_path)
        if zip_path.exists():
            zip_path.unlink()

        if task_id in self.tasks:
            del self.tasks[task_id]

        logger.info(f"Deleted task {task_id}")


storage_manager = StorageManager()
