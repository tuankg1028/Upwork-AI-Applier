import asyncio
import time
import random
from typing import Callable, Any, Optional, Dict, List, Type
from functools import wraps
from dataclasses import dataclass
from enum import Enum
from .logger import logger, TimedOperation

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for better handling"""
    NETWORK = "network"
    API = "api"
    SCRAPING = "scraping"
    DATABASE = "database"
    VALIDATION = "validation"
    PARSING = "parsing"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    UNKNOWN = "unknown"

@dataclass
class ErrorInfo:
    """Information about an error"""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception: Optional[Exception] = None
    retry_after: Optional[int] = None
    should_retry: bool = True
    max_retries: int = 3

class ErrorClassifier:
    """Classifies errors for appropriate handling"""
    
    ERROR_PATTERNS = {
        # Network errors
        "connection": ErrorInfo(ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, "Connection error", max_retries=3),
        "timeout": ErrorInfo(ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, "Timeout error", max_retries=3),
        "dns": ErrorInfo(ErrorCategory.NETWORK, ErrorSeverity.HIGH, "DNS resolution error", max_retries=2),
        
        # API errors
        "rate limit": ErrorInfo(ErrorCategory.RATE_LIMIT, ErrorSeverity.HIGH, "Rate limit exceeded", retry_after=60),
        "quota": ErrorInfo(ErrorCategory.API, ErrorSeverity.HIGH, "API quota exceeded", retry_after=300),
        "invalid api key": ErrorInfo(ErrorCategory.AUTHENTICATION, ErrorSeverity.CRITICAL, "Invalid API key", should_retry=False),
        "unauthorized": ErrorInfo(ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH, "Unauthorized access", should_retry=False),
        
        # Scraping errors
        "element not found": ErrorInfo(ErrorCategory.SCRAPING, ErrorSeverity.MEDIUM, "Element not found", max_retries=2),
        "page not loaded": ErrorInfo(ErrorCategory.SCRAPING, ErrorSeverity.MEDIUM, "Page not loaded", max_retries=3),
        "captcha": ErrorInfo(ErrorCategory.SCRAPING, ErrorSeverity.HIGH, "Captcha detected", retry_after=300),
        
        # Database errors
        "database locked": ErrorInfo(ErrorCategory.DATABASE, ErrorSeverity.MEDIUM, "Database locked", max_retries=5),
        "disk full": ErrorInfo(ErrorCategory.DATABASE, ErrorSeverity.CRITICAL, "Disk full", should_retry=False),
        
        # Validation errors
        "validation": ErrorInfo(ErrorCategory.VALIDATION, ErrorSeverity.LOW, "Validation error", should_retry=False),
        "missing field": ErrorInfo(ErrorCategory.VALIDATION, ErrorSeverity.LOW, "Missing required field", should_retry=False),
    }
    
    @classmethod
    def classify_error(cls, error: Exception) -> ErrorInfo:
        """Classify an error and return handling info"""
        error_msg = str(error).lower()
        
        for pattern, error_info in cls.ERROR_PATTERNS.items():
            if pattern in error_msg:
                return ErrorInfo(
                    category=error_info.category,
                    severity=error_info.severity,
                    message=error_info.message,
                    exception=error,
                    retry_after=error_info.retry_after,
                    should_retry=error_info.should_retry,
                    max_retries=error_info.max_retries
                )
        
        # Default classification for unknown errors
        return ErrorInfo(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            message="Unknown error",
            exception=error,
            max_retries=2
        )

class RetryStrategy:
    """Different retry strategies"""
    
    @staticmethod
    def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0, jitter: bool = True) -> float:
        """Exponential backoff with optional jitter"""
        delay = min(base_delay * (2 ** attempt), max_delay)
        if jitter:
            delay *= (0.5 + random.random() * 0.5)  # Add 0-50% jitter
        return delay
    
    @staticmethod
    def linear_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
        """Linear backoff"""
        return min(base_delay * attempt, max_delay)
    
    @staticmethod
    def fixed_delay(attempt: int, delay: float = 1.0) -> float:
        """Fixed delay"""
        return delay

class CircuitBreaker:
    """Circuit breaker pattern for failing services"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function with circuit breaker protection"""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                logger.info("Circuit breaker moving to half-open state")
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.reset()
            return result
        except Exception as e:
            self.record_failure()
            raise
    
    def record_failure(self):
        """Record a failure"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def reset(self):
        """Reset circuit breaker"""
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None
        logger.info("Circuit breaker reset to closed state")

class RobustErrorHandler:
    """Comprehensive error handling and retry system"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_stats: Dict[str, List[float]] = {}
        
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for a service"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker()
        return self.circuit_breakers[service_name]
    
    def record_error_stats(self, operation: str, error: Exception):
        """Record error statistics"""
        if operation not in self.error_stats:
            self.error_stats[operation] = []
        self.error_stats[operation].append(time.time())
        
        # Keep only last 24 hours of errors
        cutoff_time = time.time() - 86400
        self.error_stats[operation] = [
            t for t in self.error_stats[operation] if t > cutoff_time
        ]
    
    def get_error_rate(self, operation: str) -> float:
        """Get error rate for an operation (errors per hour)"""
        if operation not in self.error_stats:
            return 0.0
        
        errors_last_hour = [
            t for t in self.error_stats[operation] 
            if t > time.time() - 3600
        ]
        return len(errors_last_hour)
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        operation_name: str = None,
        use_circuit_breaker: bool = True,
        retry_strategy: Callable = RetryStrategy.exponential_backoff,
        **kwargs
    ) -> Any:
        """Execute function with retry logic and error handling"""
        
        operation_name = operation_name or func.__name__
        
        # Check if we should use circuit breaker
        if use_circuit_breaker:
            circuit_breaker = self.get_circuit_breaker(operation_name)
        
        last_error = None
        
        for attempt in range(1, 6):  # Max 5 attempts
            try:
                with TimedOperation(f"{operation_name}_attempt_{attempt}"):
                    if use_circuit_breaker:
                        result = circuit_breaker.call(func, *args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    if attempt > 1:
                        logger.info(f"Operation {operation_name} succeeded on attempt {attempt}")
                    
                    return result
                    
            except Exception as e:
                last_error = e
                error_info = ErrorClassifier.classify_error(e)
                
                # Record error stats
                self.record_error_stats(operation_name, e)
                
                # Log error details
                logger.error(
                    f"Attempt {attempt} failed for {operation_name}",
                    error=e,
                    extra={
                        "category": error_info.category.value,
                        "severity": error_info.severity.value,
                        "should_retry": error_info.should_retry,
                        "attempt": attempt
                    }
                )
                
                # Check if we should retry
                if not error_info.should_retry or attempt >= error_info.max_retries:
                    logger.error(f"Giving up on {operation_name} after {attempt} attempts")
                    break
                
                # Calculate retry delay
                if error_info.retry_after:
                    delay = error_info.retry_after
                else:
                    delay = retry_strategy(attempt - 1)
                
                logger.info(f"Retrying {operation_name} in {delay:.2f}s (attempt {attempt + 1})")
                
                # Wait before retry
                if asyncio.iscoroutinefunction(func):
                    await asyncio.sleep(delay)
                else:
                    time.sleep(delay)
        
        # If we get here, all retries failed
        logger.critical(f"All retry attempts failed for {operation_name}")
        raise last_error

# Global error handler instance
error_handler = RobustErrorHandler()

# Decorator for automatic retry
def with_retry(
    operation_name: str = None,
    use_circuit_breaker: bool = True,
    retry_strategy: Callable = RetryStrategy.exponential_backoff
):
    """Decorator for automatic retry functionality"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await error_handler.execute_with_retry(
                func,
                *args,
                operation_name=operation_name,
                use_circuit_breaker=use_circuit_breaker,
                retry_strategy=retry_strategy,
                **kwargs
            )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(error_handler.execute_with_retry(
                func,
                *args,
                operation_name=operation_name,
                use_circuit_breaker=use_circuit_breaker,
                retry_strategy=retry_strategy,
                **kwargs
            ))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

# Context manager for error handling
class ErrorContext:
    """Context manager for handling errors gracefully"""
    
    def __init__(self, operation_name: str, continue_on_error: bool = False):
        self.operation_name = operation_name
        self.continue_on_error = continue_on_error
        self.errors = []
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            error_info = ErrorClassifier.classify_error(exc_val)
            
            logger.error(
                f"Error in {self.operation_name}",
                error=exc_val,
                extra={
                    "category": error_info.category.value,
                    "severity": error_info.severity.value
                }
            )
            
            self.errors.append(exc_val)
            
            if self.continue_on_error:
                logger.warning(f"Continuing despite error in {self.operation_name}")
                return True  # Suppress the exception
            
        return False  # Don't suppress the exception