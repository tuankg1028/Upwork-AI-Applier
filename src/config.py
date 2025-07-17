import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from enum import Enum
import yaml
from .logger import logger

class ConfigFormat(Enum):
    """Supported configuration formats"""
    JSON = "json"
    YAML = "yaml"

@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "./upwork_jobs.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    max_backups: int = 7
    performance_optimization: bool = True

@dataclass
class ScrapingConfig:
    """Web scraping configuration"""
    batch_size: int = 5
    max_concurrent_pages: int = 10
    page_timeout_seconds: int = 60
    retry_failed_pages: bool = True
    max_page_retries: int = 3
    user_agent_rotation: bool = True
    respect_robots_txt: bool = True
    delay_between_requests: float = 1.0
    headless_browser: bool = True

@dataclass
class ScoringConfig:
    """Job scoring configuration"""
    minimum_score: float = 7.0
    enable_weighted_scoring: bool = True
    weights: Dict[str, float] = None
    confidence_threshold: float = 0.8
    explanation_enabled: bool = True
    custom_criteria: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.weights is None:
            self.weights = {
                "skills_match": 0.3,
                "experience_level": 0.2,
                "budget": 0.25,
                "client_history": 0.15,
                "job_description": 0.1
            }
        if self.custom_criteria is None:
            self.custom_criteria = {}

@dataclass
class LLMConfig:
    """LLM configuration"""
    default_model: str = "openai/gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: Optional[int] = None
    enable_cost_tracking: bool = True
    fallback_models: List[str] = None
    rate_limit_rpm: int = 60  # requests per minute
    timeout_seconds: int = 30
    
    def __post_init__(self):
        if self.fallback_models is None:
            self.fallback_models = [
                "openai/gpt-3.5-turbo",
                "google/gemini-pro",
                "groq/llama3-70b-8192"
            ]

@dataclass
class CoverLetterConfig:
    """Cover letter generation configuration"""
    generate_multiple_versions: bool = True
    max_versions: int = 3
    target_word_count: int = 200
    personalization_level: str = "high"  # low, medium, high
    include_keywords: bool = True
    professional_tone: bool = True
    custom_templates: Dict[str, str] = None
    
    def __post_init__(self):
        if self.custom_templates is None:
            self.custom_templates = {}

@dataclass
class InterviewConfig:
    """Interview preparation configuration"""
    generate_questions: bool = True
    include_sample_answers: bool = True
    research_client: bool = True
    industry_specific: bool = True
    confidence_tips: bool = True
    question_categories: List[str] = None
    
    def __post_init__(self):
        if self.question_categories is None:
            self.question_categories = [
                "technical_skills",
                "project_experience",
                "communication",
                "availability",
                "pricing"
            ]

@dataclass
class NotificationConfig:
    """Notification configuration"""
    enabled: bool = True
    email_notifications: bool = False
    console_notifications: bool = True
    log_level: str = "INFO"
    progress_updates: bool = True
    performance_alerts: bool = True
    error_notifications: bool = True

@dataclass
class PerformanceConfig:
    """Performance optimization configuration"""
    enable_caching: bool = True
    cache_ttl_hours: int = 24
    parallel_processing: bool = True
    max_workers: int = 4
    memory_limit_mb: int = 1024
    enable_profiling: bool = False
    optimization_level: str = "balanced"  # conservative, balanced, aggressive

@dataclass
class UpworkConfig:
    """Main application configuration"""
    
    # Core settings
    job_title: str = "AI Developer"
    max_jobs_per_run: int = 10
    run_interval_hours: int = 24
    dry_run: bool = False
    
    # Component configurations
    database: DatabaseConfig = None
    scraping: ScrapingConfig = None
    scoring: ScoringConfig = None
    llm: LLMConfig = None
    cover_letter: CoverLetterConfig = None
    interview: InterviewConfig = None
    notifications: NotificationConfig = None
    performance: PerformanceConfig = None
    
    # File paths
    profile_path: str = "./files/profile.md"
    output_path: str = "./data/cover_letter.md"
    
    # Environment settings
    environment: str = "development"  # development, production
    debug_mode: bool = False
    
    def __post_init__(self):
        # Initialize sub-configurations if not provided
        if self.database is None:
            self.database = DatabaseConfig()
        if self.scraping is None:
            self.scraping = ScrapingConfig()
        if self.scoring is None:
            self.scoring = ScoringConfig()
        if self.llm is None:
            self.llm = LLMConfig()
        if self.cover_letter is None:
            self.cover_letter = CoverLetterConfig()
        if self.interview is None:
            self.interview = InterviewConfig()
        if self.notifications is None:
            self.notifications = NotificationConfig()
        if self.performance is None:
            self.performance = PerformanceConfig()

class ConfigManager:
    """Configuration management system"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config_format = self._detect_format()
        self._config: Optional[UpworkConfig] = None
        self._load_config()
    
    def _detect_format(self) -> ConfigFormat:
        """Detect configuration file format"""
        suffix = self.config_path.suffix.lower()
        if suffix in ['.yaml', '.yml']:
            return ConfigFormat.YAML
        return ConfigFormat.JSON
    
    def _load_config(self) -> None:
        """Load configuration from file"""
        try:
            if self.config_path.exists():
                logger.info(f"Loading configuration from {self.config_path}")
                
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    if self.config_format == ConfigFormat.YAML:
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)
                
                self._config = self._dict_to_config(data)
                logger.info("Configuration loaded successfully")
            else:
                logger.info("No configuration file found, using defaults")
                self._config = UpworkConfig()
                self.save_config()  # Save default config
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Using default configuration")
            self._config = UpworkConfig()
    
    def _dict_to_config(self, data: Dict[str, Any]) -> UpworkConfig:
        """Convert dictionary to UpworkConfig"""
        # Handle nested configurations
        if 'database' in data:
            data['database'] = DatabaseConfig(**data['database'])
        if 'scraping' in data:
            data['scraping'] = ScrapingConfig(**data['scraping'])
        if 'scoring' in data:
            data['scoring'] = ScoringConfig(**data['scoring'])
        if 'llm' in data:
            data['llm'] = LLMConfig(**data['llm'])
        if 'cover_letter' in data:
            data['cover_letter'] = CoverLetterConfig(**data['cover_letter'])
        if 'interview' in data:
            data['interview'] = InterviewConfig(**data['interview'])
        if 'notifications' in data:
            data['notifications'] = NotificationConfig(**data['notifications'])
        if 'performance' in data:
            data['performance'] = PerformanceConfig(**data['performance'])
        
        return UpworkConfig(**data)
    
    def _config_to_dict(self, config: UpworkConfig) -> Dict[str, Any]:
        """Convert UpworkConfig to dictionary"""
        return asdict(config)
    
    def save_config(self) -> None:
        """Save configuration to file"""
        try:
            # Create directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = self._config_to_dict(self._config)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_format == ConfigFormat.YAML:
                    yaml.dump(data, f, default_flow_style=False, indent=2)
                else:
                    json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Configuration saved to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
    
    def get_config(self) -> UpworkConfig:
        """Get current configuration"""
        return self._config
    
    def update_config(self, **kwargs) -> None:
        """Update configuration with new values"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
                logger.info(f"Updated config: {key} = {value}")
            else:
                logger.warning(f"Unknown configuration key: {key}")
        
        self.save_config()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults"""
        logger.info("Resetting configuration to defaults")
        self._config = UpworkConfig()
        self.save_config()
    
    def validate_config(self) -> bool:
        """Validate configuration"""
        try:
            # Check required paths exist
            if not Path(self._config.profile_path).exists():
                logger.error(f"Profile file not found: {self._config.profile_path}")
                return False
            
            # Check scoring configuration
            if self._config.scoring.minimum_score < 0 or self._config.scoring.minimum_score > 10:
                logger.error("Minimum score must be between 0 and 10")
                return False
            
            # Check LLM configuration
            if not self._config.llm.default_model:
                logger.error("Default LLM model not specified")
                return False
            
            # Check batch sizes
            if self._config.scraping.batch_size <= 0:
                logger.error("Scraping batch size must be positive")
                return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def get_environment_overrides(self) -> Dict[str, Any]:
        """Get configuration overrides from environment variables"""
        overrides = {}
        
        # Environment variable mapping
        env_mapping = {
            'UPWORK_JOB_TITLE': 'job_title',
            'UPWORK_MAX_JOBS': 'max_jobs_per_run',
            'UPWORK_MIN_SCORE': 'scoring.minimum_score',
            'UPWORK_BATCH_SIZE': 'scraping.batch_size',
            'UPWORK_DEBUG': 'debug_mode',
            'UPWORK_DRY_RUN': 'dry_run',
        }
        
        for env_var, config_path in env_mapping.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                
                # Type conversion
                if config_path.endswith(('.minimum_score', '.batch_size')):
                    try:
                        value = float(value) if '.' in value else int(value)
                    except ValueError:
                        logger.warning(f"Invalid numeric value for {env_var}: {value}")
                        continue
                elif config_path.endswith(('.debug_mode', '.dry_run')):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                
                overrides[config_path] = value
        
        return overrides
    
    def apply_environment_overrides(self) -> None:
        """Apply environment variable overrides"""
        overrides = self.get_environment_overrides()
        
        for config_path, value in overrides.items():
            try:
                # Handle nested configuration paths
                if '.' in config_path:
                    parts = config_path.split('.')
                    obj = self._config
                    for part in parts[:-1]:
                        obj = getattr(obj, part)
                    setattr(obj, parts[-1], value)
                else:
                    setattr(self._config, config_path, value)
                
                logger.info(f"Applied environment override: {config_path} = {value}")
                
            except Exception as e:
                logger.error(f"Failed to apply environment override {config_path}: {e}")

# Global configuration manager
config_manager = ConfigManager()

# Convenience function to get configuration
def get_config() -> UpworkConfig:
    """Get current configuration"""
    return config_manager.get_config()

# Convenience function to update configuration
def update_config(**kwargs) -> None:
    """Update configuration"""
    config_manager.update_config(**kwargs)