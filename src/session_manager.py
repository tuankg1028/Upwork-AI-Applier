import json
import uuid
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
import threading
from dataclasses import dataclass, asdict

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .database import get_database_manager
from .state import (
    SessionInfo, SessionStatus, WorkflowCheckpoint, 
    WorkflowMetrics, MainGraphState, JobProcessingInfo, 
    JobProcessingStatus
)

@dataclass
class SessionConfig:
    """Configuration for session management"""
    enable_checkpoints: bool = True
    checkpoint_interval: int = 300  # 5 minutes
    max_sessions: int = 100
    session_timeout: int = 86400  # 24 hours
    cleanup_interval: int = 3600  # 1 hour
    backup_enabled: bool = True

class SessionManager:
    """Manages workflow sessions and state persistence"""
    
    def __init__(self, config: SessionConfig = None):
        self.config = config or SessionConfig()
        self.sessions_dir = Path("sessions")
        self.sessions_dir.mkdir(exist_ok=True)
        self.checkpoints_dir = Path("checkpoints")
        self.checkpoints_dir.mkdir(exist_ok=True)
        
        self._active_sessions: Dict[str, SessionInfo] = {}
        self._session_lock = threading.Lock()
        self._last_cleanup = datetime.now()
        
        # Load existing sessions
        self._load_existing_sessions()
        
        logger.info(f"Session manager initialized with {len(self._active_sessions)} active sessions")
    
    def _load_existing_sessions(self):
        """Load existing sessions from disk"""
        try:
            for session_file in self.sessions_dir.glob("*.json"):
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                    session_info = SessionInfo(**session_data)
                    
                    # Check if session is still valid
                    if self._is_session_valid(session_info):
                        self._active_sessions[session_info['session_id']] = session_info
                    else:
                        # Clean up expired session
                        self._cleanup_session(session_info['session_id'])
        except Exception as e:
            logger.error(f"Error loading existing sessions: {e}")
    
    def _is_session_valid(self, session_info: SessionInfo) -> bool:
        """Check if a session is still valid"""
        if session_info['status'] in [SessionStatus.COMPLETED, SessionStatus.FAILED]:
            return False
        
        # Check timeout
        if session_info['start_time']:
            start_time = datetime.fromisoformat(session_info['start_time']) if isinstance(session_info['start_time'], str) else session_info['start_time']
            if datetime.now() - start_time > timedelta(seconds=self.config.session_timeout):
                return False
        
        return True
    
    @with_retry(operation_name="create_session")
    def create_session(self, job_title: str, config_overrides: Optional[Dict[str, Any]] = None) -> str:
        """Create a new workflow session"""
        with self._session_lock:
            # Clean up old sessions if needed
            self._cleanup_expired_sessions()
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Create session info
            session_info = SessionInfo(
                session_id=session_id,
                job_title=job_title,
                start_time=datetime.now(),
                end_time=None,
                status=SessionStatus.INITIALIZING,
                total_jobs_scraped=0,
                total_jobs_scored=0,
                total_matches_found=0,
                total_applications_generated=0,
                total_applications_saved=0,
                errors=[],
                performance_metrics={}
            )
            
            # Store session
            self._active_sessions[session_id] = session_info
            self._save_session(session_info)
            
            logger.info(f"Created new session {session_id} for job title: {job_title}")
            return session_id
    
    @with_retry(operation_name="get_session")
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session information"""
        with self._session_lock:
            session = self._active_sessions.get(session_id)
            if session and not self._is_session_valid(session):
                self._cleanup_session(session_id)
                return None
            return session
    
    @with_retry(operation_name="update_session")
    def update_session(self, session_id: str, **updates) -> bool:
        """Update session information"""
        with self._session_lock:
            session = self._active_sessions.get(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for update")
                return False
            
            # Update fields
            for key, value in updates.items():
                if key in session:
                    session[key] = value
            
            # Save updated session
            self._save_session(session)
            logger.debug(f"Updated session {session_id}: {updates}")
            return True
    
    @with_retry(operation_name="complete_session")
    def complete_session(self, session_id: str, status: SessionStatus = SessionStatus.COMPLETED) -> bool:
        """Mark session as completed"""
        with self._session_lock:
            session = self._active_sessions.get(session_id)
            if not session:
                return False
            
            session['status'] = status
            session['end_time'] = datetime.now()
            
            self._save_session(session)
            logger.info(f"Session {session_id} completed with status: {status.value}")
            return True
    
    @with_retry(operation_name="save_checkpoint")
    def save_checkpoint(self, session_id: str, current_node: str, state_data: Dict[str, Any]) -> bool:
        """Save workflow checkpoint"""
        if not self.config.enable_checkpoints:
            return False
        
        try:
            checkpoint = WorkflowCheckpoint(
                session_id=session_id,
                checkpoint_time=datetime.now(),
                current_node=current_node,
                state_data=state_data,
                processing_progress=self._extract_progress(state_data)
            )
            
            checkpoint_file = self.checkpoints_dir / f"{session_id}_checkpoint.json"
            with open(checkpoint_file, 'w') as f:
                # Convert datetime objects to ISO format for JSON serialization
                checkpoint_data = self._serialize_checkpoint(checkpoint)
                json.dump(checkpoint_data, f, indent=2)
            
            logger.debug(f"Saved checkpoint for session {session_id} at node {current_node}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving checkpoint for session {session_id}: {e}")
            return False
    
    @with_retry(operation_name="load_checkpoint")
    def load_checkpoint(self, session_id: str) -> Optional[WorkflowCheckpoint]:
        """Load workflow checkpoint"""
        try:
            checkpoint_file = self.checkpoints_dir / f"{session_id}_checkpoint.json"
            if not checkpoint_file.exists():
                return None
            
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
                return self._deserialize_checkpoint(checkpoint_data)
                
        except Exception as e:
            logger.error(f"Error loading checkpoint for session {session_id}: {e}")
            return None
    
    def get_resumable_sessions(self) -> List[SessionInfo]:
        """Get list of sessions that can be resumed"""
        resumable = []
        
        for session in self._active_sessions.values():
            if (session['status'] == SessionStatus.PAUSED or 
                session['status'] in [SessionStatus.SCRAPING, SessionStatus.SCORING, SessionStatus.PROCESSING]):
                checkpoint_file = self.checkpoints_dir / f"{session['session_id']}_checkpoint.json"
                if checkpoint_file.exists():
                    resumable.append(session)
        
        return resumable
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """Get session statistics"""
        active_count = len([s for s in self._active_sessions.values() if s['status'] not in [SessionStatus.COMPLETED, SessionStatus.FAILED]])
        completed_count = len([s for s in self._active_sessions.values() if s['status'] == SessionStatus.COMPLETED])
        failed_count = len([s for s in self._active_sessions.values() if s['status'] == SessionStatus.FAILED])
        
        return {
            'total_sessions': len(self._active_sessions),
            'active_sessions': active_count,
            'completed_sessions': completed_count,
            'failed_sessions': failed_count,
            'resumable_sessions': len(self.get_resumable_sessions())
        }
    
    def cleanup_session(self, session_id: str) -> bool:
        """Manually cleanup a session"""
        return self._cleanup_session(session_id)
    
    def _cleanup_session(self, session_id: str) -> bool:
        """Clean up session files and data"""
        try:
            # Remove from active sessions
            if session_id in self._active_sessions:
                del self._active_sessions[session_id]
            
            # Remove session file
            session_file = self.sessions_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            
            # Remove checkpoint file
            checkpoint_file = self.checkpoints_dir / f"{session_id}_checkpoint.json"
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            
            logger.debug(f"Cleaned up session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")
            return False
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        if datetime.now() - self._last_cleanup < timedelta(seconds=self.config.cleanup_interval):
            return
        
        expired_sessions = []
        for session_id, session in self._active_sessions.items():
            if not self._is_session_valid(session):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self._cleanup_session(session_id)
        
        self._last_cleanup = datetime.now()
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def _save_session(self, session_info: SessionInfo):
        """Save session to disk"""
        try:
            session_file = self.sessions_dir / f"{session_info['session_id']}.json"
            with open(session_file, 'w') as f:
                # Convert datetime objects to ISO format for JSON serialization
                session_data = self._serialize_session(session_info)
                json.dump(session_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving session {session_info['session_id']}: {e}")
    
    def _serialize_session(self, session_info: SessionInfo) -> Dict[str, Any]:
        """Serialize session info for JSON storage"""
        session_data = dict(session_info)
        
        # Convert datetime objects to ISO format
        if session_data['start_time']:
            session_data['start_time'] = session_data['start_time'].isoformat()
        if session_data['end_time']:
            session_data['end_time'] = session_data['end_time'].isoformat()
        
        # Convert enum to string
        if isinstance(session_data['status'], SessionStatus):
            session_data['status'] = session_data['status'].value
        
        return session_data
    
    def _serialize_checkpoint(self, checkpoint: WorkflowCheckpoint) -> Dict[str, Any]:
        """Serialize checkpoint for JSON storage"""
        checkpoint_data = dict(checkpoint)
        
        # Convert datetime to ISO format
        if checkpoint_data['checkpoint_time']:
            checkpoint_data['checkpoint_time'] = checkpoint_data['checkpoint_time'].isoformat()
        
        return checkpoint_data
    
    def _deserialize_checkpoint(self, checkpoint_data: Dict[str, Any]) -> WorkflowCheckpoint:
        """Deserialize checkpoint from JSON"""
        if checkpoint_data['checkpoint_time']:
            checkpoint_data['checkpoint_time'] = datetime.fromisoformat(checkpoint_data['checkpoint_time'])
        
        return WorkflowCheckpoint(**checkpoint_data)
    
    def _extract_progress(self, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract progress information from state data"""
        progress = {}
        
        if 'session_info' in state_data:
            session_info = state_data['session_info']
            progress.update({
                'jobs_scraped': session_info.get('total_jobs_scraped', 0),
                'jobs_scored': session_info.get('total_jobs_scored', 0),
                'matches_found': session_info.get('total_matches_found', 0),
                'applications_generated': session_info.get('total_applications_generated', 0),
                'applications_saved': session_info.get('total_applications_saved', 0)
            })
        
        if 'scraped_jobs' in state_data:
            progress['total_jobs_to_process'] = len(state_data['scraped_jobs'])
        
        if 'job_processing_info' in state_data:
            job_info = state_data['job_processing_info']
            progress.update({
                'jobs_pending': len([j for j in job_info.values() if j['status'] == JobProcessingStatus.PENDING]),
                'jobs_processing': len([j for j in job_info.values() if j['status'] == JobProcessingStatus.PROCESSING]),
                'jobs_completed': len([j for j in job_info.values() if j['status'] in [JobProcessingStatus.SAVED, JobProcessingStatus.FAILED]])
            })
        
        return progress

class WorkflowStateManager:
    """Manages workflow state with session integration"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.current_session_id: Optional[str] = None
        self.current_state: Optional[MainGraphState] = None
        
    def initialize_session(self, job_title: str, config_overrides: Optional[Dict[str, Any]] = None) -> str:
        """Initialize a new workflow session"""
        session_id = self.session_manager.create_session(job_title, config_overrides)
        self.current_session_id = session_id
        
        # Initialize state
        self.current_state = self._create_initial_state(session_id, job_title)
        
        return session_id
    
    def resume_session(self, session_id: str) -> bool:
        """Resume an existing workflow session"""
        # Check if session exists
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False
        
        # Load checkpoint
        checkpoint = self.session_manager.load_checkpoint(session_id)
        if not checkpoint:
            logger.error(f"No checkpoint found for session {session_id}")
            return False
        
        # Restore state
        self.current_session_id = session_id
        self.current_state = MainGraphState(**checkpoint['state_data'])
        
        logger.info(f"Resumed session {session_id} from checkpoint at node {checkpoint['current_node']}")
        return True
    
    def save_checkpoint(self, current_node: str) -> bool:
        """Save current state as checkpoint"""
        if not self.current_session_id or not self.current_state:
            return False
        
        return self.session_manager.save_checkpoint(
            self.current_session_id,
            current_node,
            dict(self.current_state)
        )
    
    def update_session_progress(self, **updates) -> bool:
        """Update session progress"""
        if not self.current_session_id:
            return False
        
        return self.session_manager.update_session(self.current_session_id, **updates)
    
    def complete_session(self, status: SessionStatus = SessionStatus.COMPLETED) -> bool:
        """Complete current session"""
        if not self.current_session_id:
            return False
        
        return self.session_manager.complete_session(self.current_session_id, status)
    
    def _create_initial_state(self, session_id: str, job_title: str) -> MainGraphState:
        """Create initial workflow state"""
        session_info = SessionInfo(
            session_id=session_id,
            job_title=job_title,
            start_time=datetime.now(),
            end_time=None,
            status=SessionStatus.INITIALIZING,
            total_jobs_scraped=0,
            total_jobs_scored=0,
            total_matches_found=0,
            total_applications_generated=0,
            total_applications_saved=0,
            errors=[],
            performance_metrics={}
        )
        
        return MainGraphState(
            session_info=session_info,
            job_processing_info={},
            job_title=job_title,
            scraped_jobs=[],
            scores=[],
            jobs_processing_batch=[],
            matches=[],
            applications=[],
            failed_jobs=[],
            skipped_jobs=[],
            processing_stats={},
            config=None,
            user_profile=None,
            checkpoint_data=None,
            resume_point=None
        )

# Global session manager instance
session_manager = SessionManager()
workflow_state_manager = WorkflowStateManager(session_manager)

# Context manager for workflow sessions
@contextmanager
def workflow_session(job_title: str, config_overrides: Optional[Dict[str, Any]] = None):
    """Context manager for workflow sessions"""
    session_id = workflow_state_manager.initialize_session(job_title, config_overrides)
    
    try:
        yield session_id
        workflow_state_manager.complete_session(SessionStatus.COMPLETED)
    except Exception as e:
        logger.error(f"Workflow session {session_id} failed: {e}")
        workflow_state_manager.complete_session(SessionStatus.FAILED)
        raise
    finally:
        # Save final checkpoint
        workflow_state_manager.save_checkpoint("workflow_end")