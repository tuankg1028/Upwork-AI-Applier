import operator
from typing import Annotated, Optional, Dict, Any, List
from typing_extensions import TypedDict
from datetime import datetime
from enum import Enum

class SessionStatus(Enum):
    """Session status enumeration"""
    INITIALIZING = "initializing"
    SCRAPING = "scraping"
    SCORING = "scoring"
    PROCESSING = "processing"
    GENERATING = "generating"
    VALIDATING = "validating"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class JobProcessingStatus(Enum):
    """Job processing status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    SCORED = "scored"
    MATCHED = "matched"
    GENERATING = "generating"
    GENERATED = "generated"
    VALIDATED = "validated"
    SAVED = "saved"
    FAILED = "failed"
    SKIPPED = "skipped"

class MainGraphStateInput(TypedDict):
    job_title: str
    resume_session: Optional[str]
    config_overrides: Optional[Dict[str, Any]]

class SessionInfo(TypedDict):
    session_id: str
    job_title: str
    start_time: datetime
    end_time: Optional[datetime]
    status: SessionStatus
    total_jobs_scraped: int
    total_jobs_scored: int
    total_matches_found: int
    total_applications_generated: int
    total_applications_saved: int
    errors: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]

class JobProcessingInfo(TypedDict):
    job_id: str
    status: JobProcessingStatus
    score: Optional[float]
    score_explanation: Optional[str]
    confidence: Optional[float]
    processing_time: Optional[float]
    error_message: Optional[str]
    retry_count: int
    last_updated: datetime

class QualityMetrics(TypedDict):
    word_count: int
    readability_score: Optional[float]
    professional_tone_score: Optional[float]
    keyword_density: Optional[float]
    personalization_score: Optional[float]
    uniqueness_score: Optional[float]
    overall_quality: Optional[float]

class ApplicationInfo(TypedDict):
    job_id: str
    version: int
    cover_letter: str
    interview_preparation: str
    quality_metrics: QualityMetrics
    generated_at: datetime
    validated: bool
    validation_issues: List[str]

class MainGraphState(TypedDict):
    # Session management
    session_info: SessionInfo
    job_processing_info: Dict[str, JobProcessingInfo]
    
    # Core workflow data
    job_title: str
    scraped_jobs: List[Dict[str, Any]]
    scores: Annotated[List[Dict[str, Any]], operator.add]
    jobs_processing_batch: List[Dict[str, Any]]
    matches: List[Dict[str, Any]]
    applications: Annotated[List[ApplicationInfo], operator.add]
    
    # Enhanced tracking
    failed_jobs: List[Dict[str, Any]]
    skipped_jobs: List[Dict[str, Any]]
    processing_stats: Dict[str, Any]
    
    # Configuration and context
    config: Optional[Dict[str, Any]]
    user_profile: Optional[str]
    
    # Resume capability
    checkpoint_data: Optional[Dict[str, Any]]
    resume_point: Optional[str]

class ScoreJobsState(TypedDict):
    jobs_batch: List[Dict[str, Any]]
    batch_id: str
    processing_context: Dict[str, Any]
    
class ApplicationStateInput(TypedDict):
    job_description: str
    job_id: str
    job_context: Dict[str, Any]
    quality_requirements: Dict[str, Any]
    
class ApplicationState(TypedDict):
    job_description: str
    job_id: str
    job_context: Dict[str, Any]
    
    # Profile analysis
    relevant_infos: str
    skills_match: List[str]
    experience_relevance: str
    
    # Content generation
    cover_letter_versions: List[str]
    selected_cover_letter: str
    interview_prep: str
    
    # Quality assessment
    quality_metrics: QualityMetrics
    validation_results: Dict[str, Any]
    
    # Final output
    applications: Annotated[List[ApplicationInfo], operator.add]

class WorkflowCheckpoint(TypedDict):
    """Checkpoint data for resuming workflows"""
    session_id: str
    checkpoint_time: datetime
    current_node: str
    state_data: Dict[str, Any]
    processing_progress: Dict[str, Any]
    
class WorkflowMetrics(TypedDict):
    """Workflow performance metrics"""
    total_execution_time: float
    scraping_time: float
    scoring_time: float
    generation_time: float
    validation_time: float
    saving_time: float
    jobs_per_second: float
    applications_per_second: float
    success_rate: float
    error_rate: float
    
class QueueState(TypedDict):
    """State for job queues and processing"""
    pending_jobs: List[Dict[str, Any]]
    processing_jobs: List[Dict[str, Any]]
    completed_jobs: List[Dict[str, Any]]
    failed_jobs: List[Dict[str, Any]]
    retry_queue: List[Dict[str, Any]]