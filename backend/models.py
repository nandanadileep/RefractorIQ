import uuid
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from .database import Base # Import Base from your database.py file

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    # Define the columns for the table
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_url = Column(String, nullable=False)
    status = Column(String, default="PENDING") # e.g., PENDING, RUNNING, COMPLETED, FAILED
    error = Column(String, nullable=True) # To store error messages if the job fails
    report_s3_url = Column(String, nullable=True) # Store the path to the report file (even if local)

    # Optional: Store a summary of metrics for quick display without loading the full report
    summary_metrics = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now()) # Add default here too