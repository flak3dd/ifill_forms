import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from sqlmodel import Session, select
from .models import Job, JobStatus, ExecutionLog, LogLevel
from .database import engine
from .browser_engine import BrowserEngine
from .data_processor import DataProcessor
from .config import settings

logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self):
        self.browser_engine = BrowserEngine()
        self.data_processor = DataProcessor()
        self.running_jobs: Dict[str, asyncio.Task] = {}
        self.job_status_cache: Dict[str, Dict[str, Any]] = {}
        
    async def start(self):
        """Start the job manager"""
        await self.browser_engine.initialize()
        logger.info("Job manager started")
    
    async def stop(self):
        """Stop the job manager"""
        # Cancel all running jobs
        for job_id, task in self.running_jobs.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        await self.browser_engine.cleanup()
        logger.info("Job manager stopped")
    
    async def execute_job(self, job_id: str):
        """Execute a job"""
        if job_id in self.running_jobs:
            logger.warning(f"Job {job_id} is already running")
            return
        
        task = asyncio.create_task(self._execute_job_task(job_id))
        self.running_jobs[job_id] = task
        
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Job {job_id} was cancelled")
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            await self._update_job_status(job_id, JobStatus.FAILED, error=str(e))
        finally:
            self.running_jobs.pop(job_id, None)
    
    async def stop_job(self, job_id: str):
        """Stop a running job"""
        if job_id in self.running_jobs:
            self.running_jobs[job_id].cancel()
            await self._update_job_status(job_id, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} stopped")
    
    async def _execute_job_task(self, job_id: str):
        """Execute a job task"""
        with Session(engine) as session:
            # Get job from database
            job = session.get(Job, job_id)
            if not job:
                raise Exception(f"Job {job_id} not found")
            
            # Update job status
            await self._update_job_status(job_id, JobStatus.RUNNING)
            await self._log(job_id, LogLevel.INFO, f"Starting job execution: {job.name}")
            
            try:
                # Process data
                data = await self._load_job_data(job)
                await self._log(job_id, LogLevel.INFO, f"Loaded {len(data)} rows of data")
                
                # Execute for each row
                for i, row in enumerate(data):
                    if job_id not in self.running_jobs:  # Check if job was cancelled
                        break
                    
                    await self._process_row(job_id, job, row, i)
                    
                    # Update progress
                    progress = (i + 1) / len(data) * 100
                    await self._update_progress(job_id, i + 1, len(data))
                    
                    # Add delay between requests
                    if job.delay_between_requests > 0:
                        await asyncio.sleep(job.delay_between_requests)
                
                # Mark job as completed
                await self._update_job_status(job_id, JobStatus.COMPLETED)
                await self._log(job_id, LogLevel.INFO, f"Job completed successfully")
                
            except Exception as e:
                await self._update_job_status(job_id, JobStatus.FAILED, error=str(e))
                await self._log(job_id, LogLevel.ERROR, f"Job failed: {str(e)}")
                raise
    
    async def _load_job_data(self, job: Job) -> List[Dict[str, Any]]:
        """Load data for a job"""
        data_source = job.data_source
        
        if data_source.get("type") == "file":
            file_path = data_source.get("path")
            if not file_path:
                raise Exception("File path not specified in data source")
            
            # Get field mappings from profile
            with Session(engine) as session:
                profile = session.get(job.profile_id)
                if not profile:
                    raise Exception(f"Profile {job.profile_id} not found")
                
                mappings = profile.field_mappings or {}
                
                return await self.data_processor.process_data(file_path, mappings)
        
        elif data_source.get("type") == "sample":
            # Generate sample data for testing
            return await self.data_processor.generate_sample_data(data_source.get("num_rows", 5))
        
        else:
            raise Exception(f"Unsupported data source type: {data_source.get('type')}")
    
    async def _process_row(self, job_id: str, job: Job, row: Dict[str, Any], row_index: int):
        """Process a single row of data"""
        with Session(engine) as session:
            profile = session.get(job.profile_id)
            if not profile:
                raise Exception(f"Profile {job.profile_id} not found")
            
            try:
                # Execute the profile with the row data
                result = await self.browser_engine.execute_profile(
                    job_id, profile, row
                )
                
                if result["success"]:
                    await self._log(job_id, LogLevel.INFO, 
                                 f"Row {row_index} processed successfully", 
                                 {"row_index": row_index, "result": result})
                    
                    # Update successful count
                    job.successful_rows += 1
                    
                    # Store extracted data if any
                    if result["extracted_data"]:
                        if not job.output_data:
                            job.output_data = {}
                        job.output_data[f"row_{row_index}"] = result["extracted_data"]
                
                else:
                    await self._log(job_id, LogLevel.ERROR, 
                                 f"Row {row_index} processing failed: {result['errors']}", 
                                 {"row_index": row_index, "errors": result["errors"]})
                    
                    # Update failed count
                    job.failed_rows += 1
                    
                    # Retry if configured
                    if job.max_retries > 0:
                        await self._retry_row(job_id, job, row, row_index)
                
                # Update processed count
                job.processed_rows += 1
                session.commit()
                
            except Exception as e:
                await self._log(job_id, LogLevel.ERROR, 
                             f"Row {row_index} processing error: {str(e)}", 
                             {"row_index": row_index})
                
                job.failed_rows += 1
                job.processed_rows += 1
                session.commit()
    
    async def _retry_row(self, job_id: str, job: Job, row: Dict[str, Any], row_index: int):
        """Retry processing a row with exponential backoff"""
        for attempt in range(1, job.max_retries + 1):
            await self._log(job_id, LogLevel.WARNING, 
                         f"Retrying row {row_index}, attempt {attempt}/{job.max_retries}")
            
            # Exponential backoff
            delay = min(2 ** attempt, 30)  # Max 30 seconds
            await asyncio.sleep(delay)
            
            try:
                with Session(engine) as session:
                    profile = session.get(job.profile_id)
                    result = await self.browser_engine.execute_profile(job_id, profile, row)
                    
                    if result["success"]:
                        await self._log(job_id, LogLevel.INFO, 
                                     f"Row {row_index} succeeded on attempt {attempt}")
                        job.successful_rows += 1
                        job.failed_rows -= 1  # Remove from failed count
                        session.commit()
                        return True
                    
            except Exception as e:
                await self._log(job_id, LogLevel.ERROR, 
                             f"Row {row_index} attempt {attempt} failed: {str(e)}")
        
        return False
    
    async def _update_job_status(self, job_id: str, status: JobStatus, error: Optional[str] = None):
        """Update job status in database"""
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                job.status = status
                job.updated_at = datetime.utcnow()
                
                if status == JobStatus.RUNNING:
                    job.started_at = datetime.utcnow()
                elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    job.completed_at = datetime.utcnow()
                
                if error:
                    if not job.output_data:
                        job.output_data = {}
                    job.output_data["error"] = error
                
                session.commit()
                
                # Update cache
                self.job_status_cache[job_id] = {
                    "status": status,
                    "processed_rows": job.processed_rows,
                    "successful_rows": job.successful_rows,
                    "failed_rows": job.failed_rows,
                    "total_rows": job.total_rows
                }
    
    async def _update_progress(self, job_id: str, processed_rows: int, total_rows: int):
        """Update job progress"""
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                job.processed_rows = processed_rows
                job.updated_at = datetime.utcnow()
                
                # Estimate completion time
                if processed_rows > 0:
                    elapsed = (datetime.utcnow() - job.started_at).total_seconds()
                    avg_time_per_row = elapsed / processed_rows
                    remaining_rows = total_rows - processed_rows
                    estimated_seconds = remaining_rows * avg_time_per_row
                    job.estimated_completion = datetime.utcnow() + timedelta(seconds=estimated_seconds)
                
                session.commit()
                
                # Update cache
                self.job_status_cache[job_id] = {
                    "status": job.status,
                    "processed_rows": processed_rows,
                    "successful_rows": job.successful_rows,
                    "failed_rows": job.failed_rows,
                    "total_rows": total_rows,
                    "estimated_completion": job.estimated_completion.isoformat() if job.estimated_completion else None
                }
    
    async def _log(self, job_id: str, level: LogLevel, message: str, details: Optional[Dict[str, Any]] = None):
        """Add a log entry for a job"""
        with Session(engine) as session:
            log_entry = ExecutionLog(
                job_id=job_id,
                level=level,
                message=message,
                details=details or {}
            )
            session.add(log_entry)
            session.commit()
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get current job status"""
        # Try cache first
        if job_id in self.job_status_cache:
            return self.job_status_cache[job_id]
        
        # Load from database
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                status = {
                    "status": job.status,
                    "processed_rows": job.processed_rows,
                    "successful_rows": job.successful_rows,
                    "failed_rows": job.failed_rows,
                    "total_rows": job.total_rows,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "estimated_completion": job.estimated_completion.isoformat() if job.estimated_completion else None
                }
                self.job_status_cache[job_id] = status
                return status
        
        return {"status": "not_found"}
    
    async def get_recent_logs(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent logs for a job"""
        with Session(engine) as session:
            logs = session.exec(
                select(ExecutionLog)
                .where(ExecutionLog.job_id == job_id)
                .order_by(ExecutionLog.timestamp.desc())
                .limit(limit)
            ).all()
            
            return [
                {
                    "id": log.id,
                    "level": log.level,
                    "message": log.message,
                    "details": log.details,
                    "timestamp": log.timestamp.isoformat()
                }
                for log in logs
            ]
    
    async def pause_job(self, job_id: str):
        """Pause a job"""
        await self.stop_job(job_id)
        await self._update_job_status(job_id, JobStatus.PAUSED)
    
    async def resume_job(self, job_id: str):
        """Resume a paused job"""
        await self.execute_job(job_id)
