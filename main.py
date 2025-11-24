import asyncio
import logging
import shutil
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from config import settings
from models import TaskResponse, TaskStatusResponse, TaskStatus
from services.storage import storage_manager
from services.document_processor import processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Start background cleanup task
    cleanup_task = asyncio.create_task(storage_manager.start_cleanup_task())
    logger.info("Started storage cleanup background task")

    yield

    # Shutdown: Cancel cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Stopped storage cleanup background task")


app = FastAPI(
    title="Docling OCR Server",
    description="Document processing server with Docling and Tesseract OCR",
    version="1.0.0",
    lifespan=lifespan
)


async def process_document_task(task_id: str, file_path: Path):
    """Background task to process document"""
    try:
        logger.info(f"Processing task {task_id}")
        await storage_manager.update_task_status(task_id, TaskStatus.PROCESSING)

        # Get task directory
        task_dir = storage_manager.get_task_path(task_id)

        # Process document
        await processor.process_document(file_path, task_dir)

        # Create ZIP archive
        zip_path = storage_manager.get_zip_path(task_id)
        await asyncio.to_thread(
            shutil.make_archive,
            str(zip_path.with_suffix("")),
            "zip",
            task_dir
        )

        # Update status to completed
        await storage_manager.update_task_status(task_id, TaskStatus.COMPLETED)
        logger.info(f"Task {task_id} completed successfully")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        await storage_manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            error=str(e)
        )
    finally:
        # Clean up uploaded file
        if file_path.exists():
            file_path.unlink()


@app.post("/documents/process", response_model=TaskResponse)
async def process_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a document for processing

    Supported formats: PDF, DOCX, DOC, XLSX, XLS, JPG, PNG

    Returns task_id for tracking the processing status
    """
    # Validate file size
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    max_size = settings.max_file_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB"
        )

    # Validate file extension
    allowed_extensions = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".jpg", ".jpeg", ".png"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Create task directory
    await storage_manager.create_task(task_id)

    # Save uploaded file temporarily
    temp_file = settings.temp_storage_path / f"{task_id}_upload{file_ext}"
    try:
        with open(temp_file, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Error saving uploaded file")

    # Add background task
    background_tasks.add_task(process_document_task, task_id, temp_file)

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Document processing started"
    )


@app.get("/documents/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get processing status for a task"""
    task_info = storage_manager.get_task_status(task_id)

    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task_id,
        status=task_info["status"],
        message=f"Task is {task_info['status'].value}",
        error=task_info.get("error")
    )


@app.get("/documents/{task_id}/download")
async def download_result(task_id: str):
    """Download the processed document as ZIP"""
    task_info = storage_manager.get_task_status(task_id)

    if not task_info:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_info["status"] != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not completed. Current status: {task_info['status'].value}"
        )

    zip_path = storage_manager.get_zip_path(task_id)

    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Result file not found")

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{task_id}.zip"
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Docling OCR Server",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
