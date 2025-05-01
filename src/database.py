import sqlite3
import os
from pathlib import Path

DB_PATH = "./upwork_jobs.db"

def ensure_db_exists():
    """Ensure the database file and directory exist."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    
    if not os.path.exists(DB_PATH):
        create_tables()
    
def create_tables():
    """Create the necessary tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create jobs table to match the scraper data structure
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        title TEXT,
        link TEXT,
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def job_exists(job_id):
    """Check if a job with the given ID already exists in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
    exists = cursor.fetchone() is not None
    
    conn.close()
    return exists

def get_table_columns():
    """Get the list of columns in the jobs table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(jobs)")
    columns = [row[1] for row in cursor.fetchall()]
    
    conn.close()
    return columns

def save_job(job_data):
    """Save a job to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Extract job_id from link
    job_id = job_data.get('job_id')
    
    # Check if job already exists
    if job_exists(job_id):
        conn.close()
        return False
    
    # Get existing table columns
    table_columns = get_table_columns()
    
    # Filter job_data to only include columns that exist in the table
    filtered_job_data = {k: v for k, v in job_data.items() if k in table_columns}
    
    # Prepare columns and values for insertion
    columns = ', '.join(filtered_job_data.keys())
    placeholders = ', '.join(['?' for _ in filtered_job_data])
    values = tuple(filtered_job_data.values())
    
    # Insert the job
    cursor.execute(f"INSERT INTO jobs ({columns}) VALUES ({placeholders})", values)
    
    conn.commit()
    conn.close()
    return True

def save_jobs(jobs_data):
    """Save multiple jobs to the database and return the number of new jobs saved."""
    new_jobs_count = 0
    
    for job_data in jobs_data:
        if save_job(job_data):
            new_jobs_count += 1
    
    return new_jobs_count

def get_all_jobs():
    """Get all jobs from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    # Convert rows to dictionaries
    jobs = [dict(row) for row in rows]
    
    conn.close()
    return jobs
