from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from sqlmodel import Session, SQLModel, create_engine, select
from contextlib import asynccontextmanager
import os
from typing import List, Dict, Any, Optional
import json
import asyncio
from datetime import datetime

from .models import Profile, Job, ExecutionLog, User
from .schemas import ProfileCreate, ProfileRead, JobCreate, JobRead, JobStatus
from .database import get_session, engine
from .browser_engine import BrowserEngine
from .data_processor import DataProcessor
from .ai_mapper import AIMapper
from .job_manager import JobManager
from .api.profiles import router as profiles_router
from .api.mapping import router as mapping_router

# Configuration
from .config import settings

security = HTTPBearer()

# Global instances
browser_engine = BrowserEngine()
data_processor = DataProcessor()
ai_mapper = AIMapper()
job_manager = JobManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await browser_engine.initialize()
    await job_manager.start()
    yield
    # Shutdown
    await browser_engine.cleanup()
    await job_manager.stop()

app = FastAPI(
    title="FormForge AI API",
    description="Intelligent web form automation engine",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include new API routers
app.include_router(profiles_router)
app.include_router(mapping_router)

# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# Profile endpoints
@app.post("/api/profiles", response_model=ProfileRead)
async def create_profile(
    profile: ProfileCreate,
    session: Session = Depends(get_session)
):
    db_profile = Profile.model_validate(profile)
    session.add(db_profile)
    session.commit()
    session.refresh(db_profile)
    return db_profile

@app.get("/api/profiles", response_model=List[ProfileRead])
async def list_profiles(session: Session = Depends(get_session)):
    profiles = session.exec(select(Profile)).all()
    return profiles

@app.get("/api/profiles/{profile_id}", response_model=ProfileRead)
async def get_profile(profile_id: str, session: Session = Depends(get_session)):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@app.put("/api/profiles/{profile_id}", response_model=ProfileRead)
async def update_profile(
    profile_id: str,
    profile_update: ProfileCreate,
    session: Session = Depends(get_session)
):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile_data = profile_update.model_dump(exclude_unset=True)
    for key, value in profile_data.items():
        setattr(profile, key, value)
    
    session.commit()
    session.refresh(profile)
    return profile

@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: str, session: Session = Depends(get_session)):
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    session.delete(profile)
    session.commit()
    return {"message": "Profile deleted"}

# Site analysis endpoints
@app.post("/api/analyze-site")
async def analyze_site(url: str):
    """Analyze a website to detect forms and create a profile"""
    try:
        analysis = await ai_mapper.analyze_website(url)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/map-fields")
async def map_fields(profile_data: Dict[str, Any], csv_preview: List[Dict[str, Any]]):
    """AI-powered field mapping from CSV to profile"""
    try:
        mappings = await ai_mapper.map_fields(profile_data, csv_preview)
        return mappings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Job endpoints
@app.post("/api/jobs", response_model=JobRead)
async def create_job(
    job: JobCreate,
    session: Session = Depends(get_session)
):
    db_job = Job.model_validate(job)
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    
    # Start the job asynchronously
    asyncio.create_task(job_manager.execute_job(db_job.id))
    
    return db_job

@app.get("/api/jobs", response_model=List[JobRead])
async def list_jobs(session: Session = Depends(get_session)):
    jobs = session.exec(select(Job).order_by(Job.created_at.desc())).all()
    return jobs

@app.get("/api/jobs/{job_id}", response_model=JobRead)
async def get_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.post("/api/jobs/{job_id}/start")
async def start_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    asyncio.create_task(job_manager.execute_job(job_id))
    return {"message": "Job started"}

@app.post("/api/jobs/{job_id}/stop")
async def stop_job(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    await job_manager.stop_job(job_id)
    return {"message": "Job stopped"}

@app.get("/api/jobs/{job_id}/logs")
async def get_job_logs(job_id: str, session: Session = Depends(get_session)):
    logs = session.exec(
        select(ExecutionLog).where(ExecutionLog.job_id == job_id)
        .order_by(ExecutionLog.timestamp.desc())
    ).all()
    return logs

# File upload endpoints
@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Upload and validate CSV file"""
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file format")
    
    try:
        content = await file.read()
        analysis = await data_processor.analyze_file(content, file.filename)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint for real-time updates
@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(websocket)
    try:
        while True:
            # Send real-time updates for the job
            job_status = await job_manager.get_job_status(job_id)
            await manager.send_personal_message(
                json.dumps(job_status), websocket
            )
            await asyncio.sleep(1)  # Update every second
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Test endpoint
@app.post("/api/test-profile")
async def test_profile(
    profile_id: str,
    test_data: Dict[str, Any],
    session: Session = Depends(get_session)
):
    """Test a profile with sample data in headed mode"""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    try:
        result = await browser_engine.test_profile(profile, test_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
