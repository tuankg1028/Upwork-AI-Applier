import re
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import statistics

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config
from .utils import ainvoke_llm
from .state import QualityMetrics, ApplicationInfo

class QualityLevel(Enum):
    """Quality levels for validation"""
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"

class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    type: str
    severity: ValidationSeverity
    message: str
    suggestion: Optional[str] = None
    location: Optional[str] = None

class TextAnalyzer:
    """Analyzes text quality and characteristics"""
    
    def __init__(self):
        self.config = get_config()
        
    def analyze_readability(self, text: str) -> float:
        """Calculate readability score (Flesch Reading Ease)"""
        try:
            # Simple readability calculation
            sentences = len(re.findall(r'[.!?]+', text))
            words = len(text.split())
            syllables = self._count_syllables(text)
            
            if sentences == 0 or words == 0:
                return 0.0
            
            # Flesch Reading Ease formula
            score = 206.835 - (1.015 * (words / sentences)) - (84.6 * (syllables / words))
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error(f"Error calculating readability: {e}")
            return 0.0
    
    def _count_syllables(self, text: str) -> int:
        """Count syllables in text (approximation)"""
        vowels = "aeiouyAEIOUY"
        syllables = 0
        prev_was_vowel = False
        
        for char in text:
            if char in vowels:
                if not prev_was_vowel:
                    syllables += 1
                prev_was_vowel = True
            else:
                prev_was_vowel = False
        
        # Handle silent 'e'
        if text.endswith('e') and syllables > 1:
            syllables -= 1
        
        return max(1, syllables)
    
    def analyze_professional_tone(self, text: str) -> Tuple[float, List[str]]:
        """Analyze professional tone and return score with issues"""
        issues = []
        score = 100.0
        
        # Check for informal words
        informal_words = [
            'gonna', 'wanna', 'gotta', 'kinda', 'sorta', 'yeah', 'nah',
            'awesome', 'cool', 'super', 'totally', 'really', 'pretty'
        ]
        
        text_lower = text.lower()
        for word in informal_words:
            if word in text_lower:
                issues.append(f"Informal word: '{word}'")
                score -= 10
        
        # Check for contractions
        contractions = re.findall(r"\b\w+'\w+\b", text)
        if contractions:
            issues.append(f"Contractions found: {', '.join(contractions[:3])}")
            score -= len(contractions) * 2
        
        # Check for excessive exclamation marks
        exclamations = len(re.findall(r'!', text))
        if exclamations > 2:
            issues.append(f"Too many exclamation marks ({exclamations})")
            score -= exclamations * 5
        
        # Check for all caps words
        caps_words = re.findall(r'\b[A-Z]{3,}\b', text)
        if caps_words:
            issues.append(f"All caps words: {', '.join(caps_words[:3])}")
            score -= len(caps_words) * 10
        
        return max(0, min(100, score)), issues
    
    def calculate_keyword_density(self, text: str, keywords: List[str]) -> float:
        """Calculate keyword density"""
        if not keywords:
            return 0.0
        
        words = text.lower().split()
        total_words = len(words)
        
        if total_words == 0:
            return 0.0
        
        keyword_count = 0
        for keyword in keywords:
            keyword_count += words.count(keyword.lower())
        
        return (keyword_count / total_words) * 100
    
    def analyze_personalization(self, text: str, job_description: str) -> float:
        """Analyze how personalized the text is to the job"""
        try:
            # Extract key terms from job description
            job_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', job_description.lower()))
            text_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', text.lower()))
            
            # Calculate overlap
            overlap = len(job_words.intersection(text_words))
            total_job_words = len(job_words)
            
            if total_job_words == 0:
                return 0.0
            
            return (overlap / total_job_words) * 100
            
        except Exception as e:
            logger.error(f"Error analyzing personalization: {e}")
            return 0.0

class CoverLetterValidator:
    """Validates cover letter quality"""
    
    def __init__(self):
        self.config = get_config()
        self.text_analyzer = TextAnalyzer()
        
    @with_retry(operation_name="validate_cover_letter")
    async def validate(self, cover_letter: str, job_description: str, job_context: Dict[str, Any]) -> Tuple[QualityMetrics, List[ValidationIssue]]:
        """Validate cover letter and return quality metrics and issues"""
        with TimedOperation("cover_letter_validation"):
            issues = []
            
            # Basic validation
            basic_issues = self._validate_basic_requirements(cover_letter)
            issues.extend(basic_issues)
            
            # Structure validation
            structure_issues = self._validate_structure(cover_letter)
            issues.extend(structure_issues)
            
            # Content validation
            content_issues = await self._validate_content(cover_letter, job_description, job_context)
            issues.extend(content_issues)
            
            # Calculate quality metrics
            metrics = self._calculate_quality_metrics(cover_letter, job_description, job_context)
            
            logger.debug(f"Cover letter validation completed with {len(issues)} issues")
            return metrics, issues
    
    def _validate_basic_requirements(self, cover_letter: str) -> List[ValidationIssue]:
        """Validate basic cover letter requirements"""
        issues = []
        
        # Check length
        word_count = len(cover_letter.split())
        target_count = self.config.cover_letter.target_word_count
        
        if word_count < target_count * 0.7:
            issues.append(ValidationIssue(
                type="length",
                severity=ValidationSeverity.WARNING,
                message=f"Cover letter is too short ({word_count} words, target: {target_count})",
                suggestion="Add more specific details about your relevant experience"
            ))
        elif word_count > target_count * 1.5:
            issues.append(ValidationIssue(
                type="length",
                severity=ValidationSeverity.WARNING,
                message=f"Cover letter is too long ({word_count} words, target: {target_count})",
                suggestion="Consider making your content more concise"
            ))
        
        # Check for empty content
        if not cover_letter.strip():
            issues.append(ValidationIssue(
                type="content",
                severity=ValidationSeverity.CRITICAL,
                message="Cover letter is empty",
                suggestion="Generate cover letter content"
            ))
        
        # Check for placeholder text
        placeholders = ['[NAME]', '[COMPANY]', '[POSITION]', 'TODO', 'PLACEHOLDER']
        for placeholder in placeholders:
            if placeholder in cover_letter.upper():
                issues.append(ValidationIssue(
                    type="placeholder",
                    severity=ValidationSeverity.ERROR,
                    message=f"Found placeholder text: {placeholder}",
                    suggestion="Replace placeholder with actual content"
                ))
        
        return issues
    
    def _validate_structure(self, cover_letter: str) -> List[ValidationIssue]:
        """Validate cover letter structure"""
        issues = []
        
        # Check for greeting
        if not re.search(r'(dear|hello|hi|greetings)', cover_letter.lower()[:100]):
            issues.append(ValidationIssue(
                type="structure",
                severity=ValidationSeverity.WARNING,
                message="No greeting found at the beginning",
                suggestion="Add a professional greeting"
            ))
        
        # Check for closing
        closings = ['sincerely', 'best regards', 'thank you', 'regards', 'yours truly']
        if not any(closing in cover_letter.lower()[-200:] for closing in closings):
            issues.append(ValidationIssue(
                type="structure",
                severity=ValidationSeverity.WARNING,
                message="No professional closing found",
                suggestion="Add a professional closing"
            ))
        
        # Check paragraph structure
        paragraphs = cover_letter.split('\n\n')
        if len(paragraphs) < 3:
            issues.append(ValidationIssue(
                type="structure",
                severity=ValidationSeverity.INFO,
                message="Cover letter has fewer than 3 paragraphs",
                suggestion="Consider organizing into introduction, body, and conclusion"
            ))
        
        return issues
    
    async def _validate_content(self, cover_letter: str, job_description: str, job_context: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate cover letter content using AI"""
        issues = []
        
        try:
            # Use AI to analyze content quality
            validation_prompt = f"""
            Analyze this cover letter for a job application and identify any issues:

            Job Description:
            {job_description}

            Cover Letter:
            {cover_letter}

            Check for:
            1. Relevance to the job requirements
            2. Specific examples and achievements
            3. Generic or template-like language
            4. Spelling and grammar errors
            5. Professional tone and language

            Return a JSON object with:
            {{
                "issues": [
                    {{
                        "type": "relevance|specificity|generic|grammar|tone",
                        "severity": "info|warning|error|critical",
                        "message": "Description of the issue",
                        "suggestion": "How to fix it"
                    }}
                ]
            }}
            """
            
            response = await ainvoke_llm(
                system_prompt="You are a professional cover letter reviewer. Analyze the cover letter and provide constructive feedback.",
                user_message=validation_prompt,
                model=self.config.llm.default_model
            )
            
            # Parse AI response
            try:
                ai_feedback = json.loads(response)
                for issue_data in ai_feedback.get('issues', []):
                    issues.append(ValidationIssue(
                        type=issue_data.get('type', 'content'),
                        severity=ValidationSeverity(issue_data.get('severity', 'info')),
                        message=issue_data.get('message', ''),
                        suggestion=issue_data.get('suggestion', '')
                    ))
            except json.JSONDecodeError:
                logger.warning("Could not parse AI validation response")
                
        except Exception as e:
            logger.error(f"Error in AI content validation: {e}")
        
        return issues
    
    def _calculate_quality_metrics(self, cover_letter: str, job_description: str, job_context: Dict[str, Any]) -> QualityMetrics:
        """Calculate comprehensive quality metrics"""
        word_count = len(cover_letter.split())
        
        # Readability score
        readability_score = self.text_analyzer.analyze_readability(cover_letter)
        
        # Professional tone score
        professional_score, tone_issues = self.text_analyzer.analyze_professional_tone(cover_letter)
        
        # Keyword density
        keywords = job_context.get('keywords', [])
        keyword_density = self.text_analyzer.calculate_keyword_density(cover_letter, keywords)
        
        # Personalization score
        personalization_score = self.text_analyzer.analyze_personalization(cover_letter, job_description)
        
        # Calculate uniqueness score (simplified)
        uniqueness_score = self._calculate_uniqueness_score(cover_letter)
        
        # Calculate overall quality score
        overall_quality = statistics.mean([
            readability_score * 0.2,
            professional_score * 0.3,
            min(keyword_density * 10, 100) * 0.2,  # Cap at 10% density
            personalization_score * 0.3
        ])
        
        return QualityMetrics(
            word_count=word_count,
            readability_score=readability_score,
            professional_tone_score=professional_score,
            keyword_density=keyword_density,
            personalization_score=personalization_score,
            uniqueness_score=uniqueness_score,
            overall_quality=overall_quality
        )
    
    def _calculate_uniqueness_score(self, cover_letter: str) -> float:
        """Calculate uniqueness score based on content diversity"""
        words = cover_letter.lower().split()
        unique_words = set(words)
        
        if len(words) == 0:
            return 0.0
        
        # Calculate lexical diversity
        lexical_diversity = (len(unique_words) / len(words)) * 100
        
        # Check for common generic phrases
        generic_phrases = [
            'i am writing to apply',
            'i am interested in',
            'i would like to',
            'i am confident that',
            'i look forward to',
            'thank you for your consideration'
        ]
        
        generic_count = 0
        for phrase in generic_phrases:
            if phrase in cover_letter.lower():
                generic_count += 1
        
        # Reduce score based on generic phrases
        uniqueness_penalty = generic_count * 10
        
        return max(0, min(100, lexical_diversity - uniqueness_penalty))

class InterviewPrepValidator:
    """Validates interview preparation content"""
    
    def __init__(self):
        self.config = get_config()
        
    @with_retry(operation_name="validate_interview_prep")
    async def validate(self, interview_prep: str, job_description: str, job_context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[ValidationIssue]]:
        """Validate interview preparation content"""
        with TimedOperation("interview_prep_validation"):
            issues = []
            
            # Check for basic requirements
            if not interview_prep.strip():
                issues.append(ValidationIssue(
                    type="content",
                    severity=ValidationSeverity.CRITICAL,
                    message="Interview preparation is empty",
                    suggestion="Generate interview preparation content"
                ))
                return {}, issues
            
            # Check for question categories
            required_categories = self.config.interview.question_categories
            found_categories = []
            
            for category in required_categories:
                if category.replace('_', ' ') in interview_prep.lower():
                    found_categories.append(category)
            
            if len(found_categories) < len(required_categories) * 0.6:
                issues.append(ValidationIssue(
                    type="completeness",
                    severity=ValidationSeverity.WARNING,
                    message=f"Only {len(found_categories)} of {len(required_categories)} question categories covered",
                    suggestion="Include more diverse question categories"
                ))
            
            # Check for sample answers if configured
            if self.config.interview.include_sample_answers:
                if 'answer:' not in interview_prep.lower() and 'response:' not in interview_prep.lower():
                    issues.append(ValidationIssue(
                        type="structure",
                        severity=ValidationSeverity.INFO,
                        message="No sample answers found in interview preparation",
                        suggestion="Consider including sample answers for key questions"
                    ))
            
            # Calculate metrics
            metrics = {
                'question_count': len(re.findall(r'\?', interview_prep)),
                'categories_covered': len(found_categories),
                'word_count': len(interview_prep.split()),
                'has_sample_answers': 'answer:' in interview_prep.lower() or 'response:' in interview_prep.lower()
            }
            
            logger.debug(f"Interview preparation validation completed with {len(issues)} issues")
            return metrics, issues

class QualityValidator:
    """Main quality validation coordinator"""
    
    def __init__(self):
        self.config = get_config()
        self.cover_letter_validator = CoverLetterValidator()
        self.interview_prep_validator = InterviewPrepValidator()
        
    @with_retry(operation_name="validate_application")
    async def validate_application(self, application: ApplicationInfo, job_description: str, job_context: Dict[str, Any]) -> Tuple[bool, List[ValidationIssue]]:
        """Validate complete job application"""
        with TimedOperation("application_validation"):
            all_issues = []
            
            # Validate cover letter
            cover_letter_metrics, cover_letter_issues = await self.cover_letter_validator.validate(
                application['cover_letter'],
                job_description,
                job_context
            )
            all_issues.extend(cover_letter_issues)
            
            # Validate interview preparation
            interview_metrics, interview_issues = await self.interview_prep_validator.validate(
                application['interview_preparation'],
                job_description,
                job_context
            )
            all_issues.extend(interview_issues)
            
            # Update application with validation results
            application['quality_metrics'] = cover_letter_metrics
            application['validated'] = True
            application['validation_issues'] = [
                {
                    'type': issue.type,
                    'severity': issue.severity.value,
                    'message': issue.message,
                    'suggestion': issue.suggestion
                }
                for issue in all_issues
            ]
            
            # Determine if application passes validation
            critical_issues = [issue for issue in all_issues if issue.severity == ValidationSeverity.CRITICAL]
            error_issues = [issue for issue in all_issues if issue.severity == ValidationSeverity.ERROR]
            
            # Application passes if no critical issues and fewer than 3 error issues
            passes_validation = len(critical_issues) == 0 and len(error_issues) < 3
            
            logger.info(f"Application validation: {'PASSED' if passes_validation else 'FAILED'} with {len(all_issues)} issues")
            return passes_validation, all_issues
    
    def get_quality_level(self, quality_score: float) -> QualityLevel:
        """Get quality level based on score"""
        if quality_score >= 90:
            return QualityLevel.EXCELLENT
        elif quality_score >= 75:
            return QualityLevel.GOOD
        elif quality_score >= 60:
            return QualityLevel.FAIR
        else:
            return QualityLevel.POOR
    
    def generate_quality_report(self, application: ApplicationInfo) -> Dict[str, Any]:
        """Generate comprehensive quality report"""
        metrics = application.get('quality_metrics', {})
        issues = application.get('validation_issues', [])
        
        overall_quality = metrics.get('overall_quality', 0)
        quality_level = self.get_quality_level(overall_quality)
        
        # Group issues by severity
        issues_by_severity = {}
        for issue in issues:
            severity = issue['severity']
            if severity not in issues_by_severity:
                issues_by_severity[severity] = []
            issues_by_severity[severity].append(issue)
        
        return {
            'overall_quality_score': overall_quality,
            'quality_level': quality_level.value,
            'metrics': metrics,
            'issues_summary': {
                'total': len(issues),
                'by_severity': {k: len(v) for k, v in issues_by_severity.items()}
            },
            'issues': issues,
            'recommendations': self._generate_recommendations(metrics, issues)
        }
    
    def _generate_recommendations(self, metrics: Dict[str, Any], issues: List[Dict[str, Any]]) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        # Readability recommendations
        readability = metrics.get('readability_score', 0)
        if readability < 60:
            recommendations.append("Improve readability by using shorter sentences and simpler words")
        
        # Professional tone recommendations
        professional_score = metrics.get('professional_tone_score', 0)
        if professional_score < 80:
            recommendations.append("Enhance professional tone by avoiding informal language")
        
        # Personalization recommendations
        personalization = metrics.get('personalization_score', 0)
        if personalization < 70:
            recommendations.append("Increase personalization by including more job-specific keywords and requirements")
        
        # Keyword density recommendations
        keyword_density = metrics.get('keyword_density', 0)
        if keyword_density < 2:
            recommendations.append("Include more relevant keywords from the job description")
        elif keyword_density > 8:
            recommendations.append("Reduce keyword density to avoid appearing spammy")
        
        # Issue-based recommendations
        critical_issues = [issue for issue in issues if issue['severity'] == 'critical']
        if critical_issues:
            recommendations.append("Address critical issues before submission")
        
        error_issues = [issue for issue in issues if issue['severity'] == 'error']
        if error_issues:
            recommendations.append("Fix error-level issues to improve application quality")
        
        return recommendations

# Global validator instance
quality_validator = QualityValidator()

# Convenience functions
async def validate_cover_letter(cover_letter: str, job_description: str, job_context: Dict[str, Any]) -> Tuple[QualityMetrics, List[ValidationIssue]]:
    """Validate cover letter quality"""
    return await quality_validator.cover_letter_validator.validate(cover_letter, job_description, job_context)

async def validate_application(application: ApplicationInfo, job_description: str, job_context: Dict[str, Any]) -> Tuple[bool, List[ValidationIssue]]:
    """Validate complete application"""
    return await quality_validator.validate_application(application, job_description, job_context)