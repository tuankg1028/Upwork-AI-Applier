import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels"""
    
    COLOR_MAP = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Back.YELLOW,
    }
    
    def format(self, record):
        # Add color to level name
        level_color = self.COLOR_MAP.get(record.levelno, "")
        record.levelname = f"{level_color}{record.levelname}{Style.RESET_ALL}"
        
        # Add color to timestamp
        if hasattr(record, 'created'):
            record.asctime = f"{Fore.BLUE}{self.formatTime(record)}{Style.RESET_ALL}"
        
        return super().format(record)

class UpworkLogger:
    """Enhanced logging system for Upwork AI Applier"""
    
    def __init__(self, name: str = "upwork_ai_applier", log_level: str = "INFO"):
        self.name = name
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger = logging.getLogger(name)
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        # Clear existing handlers
        self.logger.handlers.clear()
        self.logger.setLevel(self.log_level)
        
        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        colored_formatter = ColoredFormatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(colored_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for all logs
        today = datetime.now().strftime("%Y-%m-%d")
        file_handler = logging.FileHandler(
            logs_dir / f"upwork_ai_applier_{today}.log",
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(file_handler)
        
        # Error file handler
        error_handler = logging.FileHandler(
            logs_dir / f"errors_{today}.log",
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(error_handler)
        
        # Performance log handler
        perf_handler = logging.FileHandler(
            logs_dir / f"performance_{today}.log",
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(simple_formatter)
        self.performance_logger = logging.getLogger(f"{self.name}.performance")
        self.performance_logger.addHandler(perf_handler)
        self.performance_logger.setLevel(logging.INFO)
        
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, **kwargs)
        
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, **kwargs)
        
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, **kwargs)
        
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception"""
        if error:
            self.logger.error(f"{message}: {str(error)}", exc_info=True, **kwargs)
        else:
            self.logger.error(message, **kwargs)
            
    def critical(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log critical message with optional exception"""
        if error:
            self.logger.critical(f"{message}: {str(error)}", exc_info=True, **kwargs)
        else:
            self.logger.critical(message, **kwargs)
            
    def performance(self, operation: str, duration: float, details: Optional[dict] = None):
        """Log performance metrics"""
        message = f"PERFORMANCE: {operation} took {duration:.2f}s"
        if details:
            message += f" - {details}"
        self.performance_logger.info(message)
        
    def log_job_processing(self, job_id: str, status: str, details: Optional[dict] = None):
        """Log job processing events"""
        message = f"JOB_PROCESSING: {job_id} - {status}"
        if details:
            message += f" - {details}"
        self.logger.info(message)
        
    def log_api_call(self, provider: str, model: str, tokens_used: Optional[int] = None, cost: Optional[float] = None):
        """Log API calls for monitoring usage"""
        message = f"API_CALL: {provider}/{model}"
        if tokens_used:
            message += f" - Tokens: {tokens_used}"
        if cost:
            message += f" - Cost: ${cost:.4f}"
        self.logger.info(message)
        
    def log_scraping_stats(self, total_jobs: int, new_jobs: int, skipped_jobs: int, failed_jobs: int):
        """Log scraping statistics"""
        message = f"SCRAPING_STATS: Total: {total_jobs}, New: {new_jobs}, Skipped: {skipped_jobs}, Failed: {failed_jobs}"
        self.logger.info(message)
        
    def log_application_generation(self, job_id: str, score: float, success: bool, reason: Optional[str] = None):
        """Log application generation results"""
        status = "SUCCESS" if success else "FAILED"
        message = f"APPLICATION_GEN: {job_id} (Score: {score}) - {status}"
        if reason:
            message += f" - {reason}"
        self.logger.info(message)

# Global logger instance
logger = UpworkLogger()

# Context manager for timing operations
class TimedOperation:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str, log_performance: bool = True):
        self.operation_name = operation_name
        self.log_performance = log_performance
        self.start_time = None
        
    def __enter__(self):
        self.start_time = datetime.now()
        logger.debug(f"Starting operation: {self.operation_name}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            if exc_type:
                logger.error(f"Operation failed: {self.operation_name} after {duration:.2f}s", error=exc_val)
            else:
                logger.debug(f"Operation completed: {self.operation_name} in {duration:.2f}s")
                if self.log_performance:
                    logger.performance(self.operation_name, duration)

# Decorator for logging function calls
def log_function_call(log_args: bool = False, log_result: bool = False):
    """Decorator to log function calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__name__}"
            
            # Log function start
            if log_args:
                logger.debug(f"Calling {func_name} with args: {args}, kwargs: {kwargs}")
            else:
                logger.debug(f"Calling {func_name}")
            
            try:
                with TimedOperation(func_name):
                    result = func(*args, **kwargs)
                
                # Log function result
                if log_result:
                    logger.debug(f"{func_name} returned: {result}")
                
                return result
                
            except Exception as e:
                logger.error(f"Error in {func_name}", error=e)
                raise
                
        return wrapper
    return decorator