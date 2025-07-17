import sqlite3
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config

DB_PATH = "./upwork_jobs.db"

class DatabaseManager:
    """Enhanced database manager with performance optimizations"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.config = get_config()
        self._ensure_db_exists()
        self._optimize_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            # Optimize for performance
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _ensure_db_exists(self):
        """Ensure the database file and directory exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        if not os.path.exists(self.db_path):
            logger.info("Creating new database")
            self._create_tables()
        else:
            logger.debug("Database already exists")
            self._migrate_schema()
    
    def _create_tables(self):
        """Create the necessary tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create jobs table with enhanced schema
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                link TEXT UNIQUE NOT NULL,
                job_type TEXT,
                experience_level TEXT,
                duration TEXT,
                payment_rate TEXT,
                score REAL,
                description TEXT,
                proposal_requirements TEXT,
                client_joined_date TEXT,
                client_location TEXT,
                client_total_spent TEXT,
                client_total_hires INTEGER,
                client_company_profile TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'new',
                applied_at TIMESTAMP,
                application_id TEXT,
                response_received BOOLEAN DEFAULT FALSE,
                response_at TIMESTAMP,
                response_type TEXT,
                hired BOOLEAN DEFAULT FALSE,
                hired_at TIMESTAMP,
                project_value REAL,
                notes TEXT
            )
            ''')
            
            # Create applications table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                cover_letter TEXT NOT NULL,
                interview_preparation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version INTEGER DEFAULT 1,
                quality_score REAL,
                word_count INTEGER,
                keywords TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs (job_id)
            )
            ''')
            
            # Create performance metrics table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
            ''')
            
            # Create error logs table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved BOOLEAN DEFAULT FALSE
            )
            ''')
            
            # Create indexes for better performance
            self._create_indexes(cursor)
            
            conn.commit()
            logger.info("Database tables created successfully")
    
    def _create_indexes(self, cursor):
        """Create database indexes for better performance"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs(job_type)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_experience_level ON jobs(experience_level)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_title ON jobs(title)",
            "CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id)",
            "CREATE INDEX IF NOT EXISTS idx_applications_created_at ON applications(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_performance_operation ON performance_metrics(operation)",
            "CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance_metrics(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_error_logs_timestamp ON error_logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_error_logs_operation ON error_logs(operation)",
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except sqlite3.Error as e:
                logger.warning(f"Could not create index: {e}")
    
    def _migrate_schema(self):
        """Migrate database schema if needed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if new columns exist, add if missing
            cursor.execute("PRAGMA table_info(jobs)")
            columns = [column[1] for column in cursor.fetchall()]
            
            new_columns = [
                ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("status", "TEXT DEFAULT 'new'"),
                ("applied_at", "TIMESTAMP"),
                ("application_id", "TEXT"),
                ("response_received", "BOOLEAN DEFAULT FALSE"),
                ("response_at", "TIMESTAMP"),
                ("response_type", "TEXT"),
                ("hired", "BOOLEAN DEFAULT FALSE"),
                ("hired_at", "TIMESTAMP"),
                ("project_value", "REAL"),
                ("notes", "TEXT")
            ]
            
            for column_name, column_def in new_columns:
                if column_name not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_def}")
                        logger.info(f"Added column {column_name} to jobs table")
                    except sqlite3.Error as e:
                        logger.warning(f"Could not add column {column_name}: {e}")
            
            # Create new tables if they don't exist
            self._create_tables()
            conn.commit()
    
    def _optimize_database(self):
        """Optimize database performance"""
        if not self.config.database.performance_optimization:
            return
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Run ANALYZE to update table statistics
            cursor.execute("ANALYZE")
            
            # Clean up old data if configured
            self._cleanup_old_data(cursor)
            
            conn.commit()
    
    def _cleanup_old_data(self, cursor):
        """Clean up old data based on configuration"""
        # Remove old performance metrics (keep last 30 days)
        cutoff_date = datetime.now() - timedelta(days=30)
        cursor.execute(
            "DELETE FROM performance_metrics WHERE timestamp < ?",
            (cutoff_date,)
        )
        
        # Remove old error logs (keep last 7 days)
        cutoff_date = datetime.now() - timedelta(days=7)
        cursor.execute(
            "DELETE FROM error_logs WHERE timestamp < ? AND resolved = TRUE",
            (cutoff_date,)
        )
        
        # Remove old job applications (keep last 90 days)
        cutoff_date = datetime.now() - timedelta(days=90)
        cursor.execute(
            "DELETE FROM applications WHERE created_at < ?",
            (cutoff_date,)
        )
        
        logger.info("Database cleanup completed")
    
    @with_retry(operation_name="database_backup")
    def backup_database(self, backup_path: str = None) -> str:
        """Create a backup of the database"""
        if not self.config.database.backup_enabled:
            logger.info("Database backup disabled in configuration")
            return None
        
        if backup_path is None:
            backup_dir = Path("backups")
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"upwork_jobs_backup_{timestamp}.db"
        
        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            
            # Clean up old backups
            self._cleanup_old_backups(backup_dir)
            
            return str(backup_path)
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            raise
    
    def _cleanup_old_backups(self, backup_dir: Path):
        """Clean up old backup files"""
        max_backups = self.config.database.max_backups
        
        backup_files = sorted(
            backup_dir.glob("upwork_jobs_backup_*.db"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for backup_file in backup_files[max_backups:]:
            try:
                backup_file.unlink()
                logger.debug(f"Deleted old backup: {backup_file}")
            except Exception as e:
                logger.warning(f"Could not delete old backup {backup_file}: {e}")

# Global database manager instance
db_manager = DatabaseManager()

def ensure_db_exists():
    """Ensure the database file and directory exist."""
    db_manager._ensure_db_exists()

def create_tables():
    """Create the necessary tables if they don't exist."""
    db_manager._create_tables()

@with_retry(operation_name="job_exists_check")
def job_exists(job_id: str) -> bool:
    """Check if a job with the given ID already exists in the database."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
        return cursor.fetchone() is not None

@with_retry(operation_name="get_table_columns")
def get_table_columns() -> List[str]:
    """Get the list of columns in the jobs table."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(jobs)")
        return [row[1] for row in cursor.fetchall()]

@with_retry(operation_name="save_job")
def save_job(job_data: Dict[str, Any]) -> bool:
    """Save a job to the database."""
    with TimedOperation("save_job"):
        job_id = job_data.get('job_id')
        
        if not job_id:
            logger.error("Job data missing job_id")
            return False
        
        # Check if job already exists
        if job_exists(job_id):
            logger.debug(f"Job {job_id} already exists, skipping")
            return False
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get existing table columns
            cursor.execute("PRAGMA table_info(jobs)")
            table_columns = [row[1] for row in cursor.fetchall()]
            
            # Filter job_data to only include columns that exist in the table
            filtered_job_data = {k: v for k, v in job_data.items() if k in table_columns}
            
            # Add timestamp if not present
            if 'created_at' not in filtered_job_data:
                filtered_job_data['created_at'] = datetime.now().isoformat()
            
            # Prepare columns and values for insertion
            columns = ', '.join(filtered_job_data.keys())
            placeholders = ', '.join(['?' for _ in filtered_job_data])
            values = tuple(filtered_job_data.values())
            
            # Insert the job
            cursor.execute(f"INSERT INTO jobs ({columns}) VALUES ({placeholders})", values)
            conn.commit()
            
            logger.debug(f"Saved job {job_id} to database")
            return True

@with_retry(operation_name="save_jobs_batch")
def save_jobs(jobs_data: List[Dict[str, Any]]) -> int:
    """Save multiple jobs to the database and return the number of new jobs saved."""
    if not jobs_data:
        logger.warning("No jobs data provided to save")
        return 0
    
    with TimedOperation("save_jobs_batch"):
        new_jobs_count = 0
        failed_jobs = []
        
        for job_data in jobs_data:
            try:
                if save_job(job_data):
                    new_jobs_count += 1
            except Exception as e:
                failed_jobs.append(job_data.get('job_id', 'unknown'))
                logger.error(f"Failed to save job: {e}")
        
        if failed_jobs:
            logger.warning(f"Failed to save {len(failed_jobs)} jobs: {failed_jobs}")
        
        logger.info(f"Successfully saved {new_jobs_count} new jobs out of {len(jobs_data)} total")
        return new_jobs_count

@with_retry(operation_name="get_all_jobs")
def get_all_jobs(limit: Optional[int] = None, offset: int = 0, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Get all jobs from the database with optional filtering and pagination."""
    with TimedOperation("get_all_jobs"):
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query with filters
            query = "SELECT * FROM jobs"
            params = []
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    if key == 'min_score':
                        conditions.append("score >= ?")
                        params.append(value)
                    elif key == 'job_type':
                        conditions.append("job_type = ?")
                        params.append(value)
                    elif key == 'status':
                        conditions.append("status = ?")
                        params.append(value)
                    elif key == 'date_from':
                        conditions.append("created_at >= ?")
                        params.append(value)
                    elif key == 'date_to':
                        conditions.append("created_at <= ?")
                        params.append(value)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY created_at DESC"
            
            if limit:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert rows to dictionaries
            jobs = [dict(row) for row in rows]
            
            logger.debug(f"Retrieved {len(jobs)} jobs from database")
            return jobs

@with_retry(operation_name="get_job_by_id")
def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific job by ID."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

@with_retry(operation_name="update_job_status")
def update_job_status(job_id: str, status: str, **kwargs) -> bool:
    """Update job status and additional fields."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        
        # Build update query
        updates = ["status = ?", "updated_at = ?"]
        params = [status, datetime.now().isoformat()]
        
        # Add additional fields
        for key, value in kwargs.items():
            if key in ['applied_at', 'response_at', 'hired_at', 'project_value', 'notes']:
                updates.append(f"{key} = ?")
                params.append(value)
        
        params.append(job_id)
        
        query = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?"
        cursor.execute(query, params)
        conn.commit()
        
        success = cursor.rowcount > 0
        if success:
            logger.info(f"Updated job {job_id} status to {status}")
        else:
            logger.warning(f"Job {job_id} not found for status update")
        
        return success

@with_retry(operation_name="save_application")
def save_application(job_id: str, cover_letter: str, interview_preparation: str, **kwargs) -> int:
    """Save a job application to the database."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        
        # Count existing applications for this job
        cursor.execute("SELECT COUNT(*) FROM applications WHERE job_id = ?", (job_id,))
        version = cursor.fetchone()[0] + 1
        
        # Calculate metrics
        word_count = len(cover_letter.split())
        
        cursor.execute('''
            INSERT INTO applications (
                job_id, cover_letter, interview_preparation, version,
                word_count, quality_score, keywords
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_id, cover_letter, interview_preparation, version,
            word_count, kwargs.get('quality_score'), kwargs.get('keywords')
        ))
        
        conn.commit()
        application_id = cursor.lastrowid
        
        logger.info(f"Saved application {application_id} for job {job_id}")
        return application_id

@with_retry(operation_name="get_job_statistics")
def get_job_statistics() -> Dict[str, Any]:
    """Get job statistics from the database."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        
        stats = {}
        
        # Total jobs
        cursor.execute("SELECT COUNT(*) FROM jobs")
        stats['total_jobs'] = cursor.fetchone()[0]
        
        # Jobs by status
        cursor.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")
        stats['jobs_by_status'] = dict(cursor.fetchall())
        
        # Average score
        cursor.execute("SELECT AVG(score) FROM jobs WHERE score IS NOT NULL")
        avg_score = cursor.fetchone()[0]
        stats['average_score'] = round(avg_score, 2) if avg_score else 0
        
        # Score distribution
        cursor.execute('''
            SELECT 
                CASE 
                    WHEN score >= 9 THEN 'excellent'
                    WHEN score >= 7 THEN 'good'
                    WHEN score >= 5 THEN 'average'
                    ELSE 'poor'
                END as score_category,
                COUNT(*) 
            FROM jobs 
            WHERE score IS NOT NULL 
            GROUP BY score_category
        ''')
        stats['score_distribution'] = dict(cursor.fetchall())
        
        # Jobs by type
        cursor.execute("SELECT job_type, COUNT(*) FROM jobs GROUP BY job_type")
        stats['jobs_by_type'] = dict(cursor.fetchall())
        
        # Recent activity (last 7 days)
        cursor.execute('''
            SELECT COUNT(*) FROM jobs 
            WHERE created_at >= date('now', '-7 days')
        ''')
        stats['recent_jobs'] = cursor.fetchone()[0]
        
        logger.debug(f"Generated job statistics: {stats}")
        return stats

@with_retry(operation_name="log_performance_metric")
def log_performance_metric(operation: str, duration: float, success: bool, error_message: str = None, metadata: Dict[str, Any] = None):
    """Log a performance metric to the database."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO performance_metrics (
                operation, duration_seconds, success, error_message, metadata
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            operation, duration, success, error_message, 
            json.dumps(metadata) if metadata else None
        ))
        
        conn.commit()

@with_retry(operation_name="log_error")
def log_error(operation: str, error_type: str, error_message: str, stack_trace: str = None):
    """Log an error to the database."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO error_logs (
                operation, error_type, error_message, stack_trace
            ) VALUES (?, ?, ?, ?)
        ''', (operation, error_type, error_message, stack_trace))
        
        conn.commit()

def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    return db_manager
