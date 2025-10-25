import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

# Create the Celery application instance
celery_app = Celery(
    "RefractorIQ-Worker", # Name of the worker
    broker=os.getenv("CELERY_BROKER_URL"), # Connection string for Redis (the queue)
    backend=os.getenv("CELERY_RESULT_BACKEND"), # Connection string for Redis (to store results)
    include=["backend.tasks"] # Tells Celery where to find your task functions (in tasks.py)
)

# Optional configuration (can be useful)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"], # Allow JSON content
    result_serializer="json",
    timezone="UTC", # Use UTC timezone
    enable_utc=True,
)

# Example of how to start the worker directly (usually done via CLI)
if __name__ == "__main__":
    # This part is mostly for reference; you'll run the worker using the celery CLI command.
    celery_app.start()

    