from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from enum import Enum

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Enums
class TechStack(str, Enum):
    NODEJS = "nodejs"
    PYTHON = "python"
    JAVA = "java"
    DOTNET = "dotnet"
    REACT = "react"
    ANGULAR = "angular"
    VUE = "vue"

class BuildTool(str, Enum):
    MAVEN = "maven"
    GRADLE = "gradle"
    NPM = "npm"
    YARN = "yarn"
    PIP = "pip"

class CloudProvider(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ON_PREMISE = "on-premise"

class DeploymentType(str, Enum):
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    VM = "vm"
    SERVERLESS = "serverless"

class CICDTool(str, Enum):
    JENKINS = "jenkins"
    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"

class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"

class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

# Models
class Application(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    tech_stack: List[TechStack]
    build_tool: BuildTool
    deployment_type: DeploymentType
    cloud_provider: CloudProvider
    cicd_tool: CICDTool
    repository_url: str
    branch: str = "main"
    security_checks: List[str] = ["sonarqube", "trivy", "cycode"]
    notification_emails: List[str]
    resource_manager_email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ApplicationCreate(BaseModel):
    name: str
    description: str
    tech_stack: List[TechStack]
    build_tool: BuildTool
    deployment_type: DeploymentType
    cloud_provider: CloudProvider
    cicd_tool: CICDTool
    repository_url: str
    branch: str = "main"
    security_checks: List[str]
    notification_emails: List[str]
    resource_manager_email: str

class PipelineStage(BaseModel):
    name: str
    status: StageStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    logs: List[str] = []
    duration_seconds: Optional[int] = None

class Pipeline(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str
    application_name: str
    status: PipelineStatus
    stages: List[PipelineStage] = []
    environment: str = "dev"  # dev, uat, production
    triggered_by: str
    approval_status: Optional[str] = None
    approved_by: Optional[str] = None
    approval_comment: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[int] = None

class PipelineCreate(BaseModel):
    application_id: str
    environment: str = "dev"
    triggered_by: str

class ApprovalRequest(BaseModel):
    approved: bool
    approved_by: str
    comment: Optional[str] = None

class DashboardStats(BaseModel):
    total_applications: int
    total_pipelines: int
    success_rate: float
    pipelines_today: int
    pending_approvals: int

# Onboarding Endpoints
@api_router.post("/applications", response_model=Application)
async def create_application(input: ApplicationCreate):
    """Onboard a new application"""
    app_dict = input.model_dump()
    app_obj = Application(**app_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = app_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    
    _ = await db.applications.insert_one(doc)
    return app_obj

@api_router.get("/applications", response_model=List[Application])
async def get_applications():
    """Get all onboarded applications"""
    apps = await db.applications.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for app in apps:
        if isinstance(app['created_at'], str):
            app['created_at'] = datetime.fromisoformat(app['created_at'])
        if isinstance(app['updated_at'], str):
            app['updated_at'] = datetime.fromisoformat(app['updated_at'])
    
    return apps

@api_router.get("/applications/{app_id}", response_model=Application)
async def get_application(app_id: str):
    """Get application by ID"""
    app = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    if isinstance(app['created_at'], str):
        app['created_at'] = datetime.fromisoformat(app['created_at'])
    if isinstance(app['updated_at'], str):
        app['updated_at'] = datetime.fromisoformat(app['updated_at'])
    
    return app

@api_router.delete("/applications/{app_id}")
async def delete_application(app_id: str):
    """Delete an application"""
    result = await db.applications.delete_one({"id": app_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"message": "Application deleted successfully"}

# Pipeline Execution Endpoints
@api_router.post("/pipelines", response_model=Pipeline)
async def trigger_pipeline(input: PipelineCreate):
    """Trigger a new pipeline execution"""
    # Get application details
    app = await db.applications.find_one({"id": input.application_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Create pipeline stages based on application configuration
    stages = [
        PipelineStage(name="Checkout Code", status=StageStatus.PENDING),
        PipelineStage(name="Build", status=StageStatus.PENDING),
        PipelineStage(name="Unit Tests", status=StageStatus.PENDING),
    ]
    
    # Add security scans
    for check in app.get('security_checks', []):
        stages.append(PipelineStage(name=f"Security Scan - {check.upper()}", status=StageStatus.PENDING))
    
    # Add deployment stage
    if input.environment == "production":
        stages.append(PipelineStage(name="Approval Gate", status=StageStatus.PENDING))
    
    stages.append(PipelineStage(name=f"Deploy to {input.environment.upper()}", status=StageStatus.PENDING))
    
    pipeline = Pipeline(
        application_id=input.application_id,
        application_name=app['name'],
        status=PipelineStatus.PENDING,
        stages=stages,
        environment=input.environment,
        triggered_by=input.triggered_by
    )
    
    doc = pipeline.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    
    # Convert stages
    for stage in doc['stages']:
        if stage.get('started_at'):
            stage['started_at'] = stage['started_at'].isoformat() if isinstance(stage['started_at'], datetime) else stage['started_at']
        if stage.get('completed_at'):
            stage['completed_at'] = stage['completed_at'].isoformat() if isinstance(stage['completed_at'], datetime) else stage['completed_at']
    
    _ = await db.pipelines.insert_one(doc)
    return pipeline

@api_router.get("/pipelines", response_model=List[Pipeline])
async def get_pipelines(application_id: Optional[str] = None, status: Optional[PipelineStatus] = None):
    """Get all pipelines with optional filters"""
    query = {}
    if application_id:
        query['application_id'] = application_id
    if status:
        query['status'] = status
    
    pipelines = await db.pipelines.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Convert ISO strings back to datetime
    for pipeline in pipelines:
        if isinstance(pipeline['created_at'], str):
            pipeline['created_at'] = datetime.fromisoformat(pipeline['created_at'])
        if isinstance(pipeline['updated_at'], str):
            pipeline['updated_at'] = datetime.fromisoformat(pipeline['updated_at'])
        if pipeline.get('completed_at') and isinstance(pipeline['completed_at'], str):
            pipeline['completed_at'] = datetime.fromisoformat(pipeline['completed_at'])
        
        for stage in pipeline.get('stages', []):
            if stage.get('started_at') and isinstance(stage['started_at'], str):
                stage['started_at'] = datetime.fromisoformat(stage['started_at'])
            if stage.get('completed_at') and isinstance(stage['completed_at'], str):
                stage['completed_at'] = datetime.fromisoformat(stage['completed_at'])
    
    return pipelines

@api_router.get("/pipelines/{pipeline_id}", response_model=Pipeline)
async def get_pipeline(pipeline_id: str):
    """Get pipeline by ID"""
    pipeline = await db.pipelines.find_one({"id": pipeline_id}, {"_id": 0})
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if isinstance(pipeline['created_at'], str):
        pipeline['created_at'] = datetime.fromisoformat(pipeline['created_at'])
    if isinstance(pipeline['updated_at'], str):
        pipeline['updated_at'] = datetime.fromisoformat(pipeline['updated_at'])
    if pipeline.get('completed_at') and isinstance(pipeline['completed_at'], str):
        pipeline['completed_at'] = datetime.fromisoformat(pipeline['completed_at'])
    
    for stage in pipeline.get('stages', []):
        if stage.get('started_at') and isinstance(stage['started_at'], str):
            stage['started_at'] = datetime.fromisoformat(stage['started_at'])
        if stage.get('completed_at') and isinstance(stage['completed_at'], str):
            stage['completed_at'] = datetime.fromisoformat(stage['completed_at'])
    
    return pipeline

@api_router.post("/pipelines/{pipeline_id}/simulate")
async def simulate_pipeline_execution(pipeline_id: str):
    """Simulate pipeline execution (mock for MVP)"""
    import random
    import asyncio
    
    pipeline = await db.pipelines.find_one({"id": pipeline_id}, {"_id": 0})
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    # Update pipeline status to running
    await db.pipelines.update_one(
        {"id": pipeline_id},
        {"$set": {"status": PipelineStatus.RUNNING.value, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Simulate stage execution
    stages = pipeline['stages']
    for i, stage in enumerate(stages):
        # Random success/failure (90% success rate)
        success = random.random() > 0.1
        
        # Update stage to running
        stages[i]['status'] = StageStatus.RUNNING.value
        stages[i]['started_at'] = datetime.now(timezone.utc).isoformat()
        stages[i]['logs'] = [f"Starting {stage['name']}...", f"Executing {stage['name']} tasks..."]
        
        await db.pipelines.update_one(
            {"id": pipeline_id},
            {"$set": {"stages": stages, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Simulate work
        await asyncio.sleep(0.5)
        
        # Update stage completion
        duration = random.randint(5, 30)
        stages[i]['status'] = StageStatus.SUCCESS.value if success else StageStatus.FAILED.value
        stages[i]['completed_at'] = datetime.now(timezone.utc).isoformat()
        stages[i]['duration_seconds'] = duration
        stages[i]['logs'].append(f"{stage['name']} completed {'successfully' if success else 'with errors'}")
        
        await db.pipelines.update_one(
            {"id": pipeline_id},
            {"$set": {"stages": stages, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        # If stage failed, mark pipeline as failed
        if not success:
            await db.pipelines.update_one(
                {"id": pipeline_id},
                {"$set": {
                    "status": PipelineStatus.FAILED.value,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            return {"message": "Pipeline execution failed", "pipeline_id": pipeline_id}
    
    # Check if needs approval
    if pipeline['environment'] == 'production':
        await db.pipelines.update_one(
            {"id": pipeline_id},
            {"$set": {
                "status": PipelineStatus.WAITING_APPROVAL.value,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return {"message": "Pipeline awaiting approval", "pipeline_id": pipeline_id}
    
    # Mark pipeline as successful
    await db.pipelines.update_one(
        {"id": pipeline_id},
        {"$set": {
            "status": PipelineStatus.SUCCESS.value,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"message": "Pipeline executed successfully", "pipeline_id": pipeline_id}

# Approval Workflow Endpoints
@api_router.post("/pipelines/{pipeline_id}/approve")
async def approve_pipeline(pipeline_id: str, approval: ApprovalRequest):
    """Approve or reject a pipeline"""
    pipeline = await db.pipelines.find_one({"id": pipeline_id}, {"_id": 0})
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if pipeline['status'] != PipelineStatus.WAITING_APPROVAL.value:
        raise HTTPException(status_code=400, detail="Pipeline is not waiting for approval")
    
    new_status = PipelineStatus.APPROVED.value if approval.approved else PipelineStatus.REJECTED.value
    
    update_data = {
        "status": new_status,
        "approval_status": "approved" if approval.approved else "rejected",
        "approved_by": approval.approved_by,
        "approval_comment": approval.comment,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if not approval.approved:
        update_data["completed_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.pipelines.update_one(
        {"id": pipeline_id},
        {"$set": update_data}
    )
    
    return {"message": f"Pipeline {'approved' if approval.approved else 'rejected'} successfully"}

@api_router.get("/pipelines/pending-approvals", response_model=List[Pipeline])
async def get_pending_approvals():
    """Get all pipelines waiting for approval"""
    pipelines = await db.pipelines.find(
        {"status": PipelineStatus.WAITING_APPROVAL.value},
        {"_id": 0}
    ).to_list(1000)
    
    for pipeline in pipelines:
        if isinstance(pipeline['created_at'], str):
            pipeline['created_at'] = datetime.fromisoformat(pipeline['created_at'])
        if isinstance(pipeline['updated_at'], str):
            pipeline['updated_at'] = datetime.fromisoformat(pipeline['updated_at'])
    
    return pipelines

# Dashboard Endpoints
@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get dashboard statistics"""
    total_applications = await db.applications.count_documents({})
    total_pipelines = await db.pipelines.count_documents({})
    
    # Calculate success rate
    successful_pipelines = await db.pipelines.count_documents({"status": PipelineStatus.SUCCESS.value})
    success_rate = (successful_pipelines / total_pipelines * 100) if total_pipelines > 0 else 0
    
    # Pipelines today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    pipelines_today = await db.pipelines.count_documents({
        "created_at": {"$gte": today_start.isoformat()}
    })
    
    # Pending approvals
    pending_approvals = await db.pipelines.count_documents({"status": PipelineStatus.WAITING_APPROVAL.value})
    
    return DashboardStats(
        total_applications=total_applications,
        total_pipelines=total_pipelines,
        success_rate=round(success_rate, 2),
        pipelines_today=pipelines_today,
        pending_approvals=pending_approvals
    )

@api_router.get("/")
async def root():
    return {"message": "CI/CD Orchestration Platform API"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
