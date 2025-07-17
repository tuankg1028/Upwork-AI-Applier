import re
import json
import asyncio
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import nltk
from textstat import flesch_reading_ease, automated_readability_index, flesch_kincaid_grade
from collections import Counter
import spacy

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config
from .utils import ainvoke_llm

# Download required NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('vader_lexicon', quiet=True)
except:
    pass

class QualityDimension(Enum):
    """Quality dimensions for comprehensive assessment"""
    READABILITY = "readability"
    PROFESSIONALISM = "professionalism"
    PERSONALIZATION = "personalization"
    TECHNICAL_ACCURACY = "technical_accuracy"
    PERSUASIVENESS = "persuasiveness"
    STRUCTURE = "structure"
    RELEVANCE = "relevance"
    COMPLETENESS = "completeness"
    GRAMMAR = "grammar"
    TONE_CONSISTENCY = "tone_consistency"

class QualityLevel(Enum):
    """Quality levels for assessment"""
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
class QualityMetric:
    """Individual quality metric"""
    dimension: QualityDimension
    score: float
    level: QualityLevel
    weight: float
    details: str
    recommendations: List[str]

@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    type: str
    severity: ValidationSeverity
    message: str
    suggestion: Optional[str] = None
    location: Optional[str] = None
    confidence: float = 1.0

@dataclass
class QualityAssessment:
    """Comprehensive quality assessment"""
    overall_score: float
    overall_level: QualityLevel
    metrics: List[QualityMetric]
    issues: List[ValidationIssue]
    recommendations: List[str]
    strengths: List[str]
    improvement_areas: List[str]
    confidence: float
    assessment_timestamp: datetime

class AdvancedTextAnalyzer:
    """Advanced text analysis with NLP capabilities"""
    
    def __init__(self):
        self.config = get_config()
        
        # Initialize NLP models
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found, using basic analysis")
            self.nlp = None
        
        # Professional vocabulary patterns
        self.professional_indicators = {
            'expertise_words': [
                'expertise', 'proficiency', 'specialization', 'competency',
                'mastery', 'skilled', 'experienced', 'qualified'
            ],
            'business_terms': [
                'deliverables', 'stakeholders', 'requirements', 'objectives',
                'strategy', 'implementation', 'optimization', 'efficiency'
            ],
            'action_verbs': [
                'developed', 'implemented', 'designed', 'created', 'managed',
                'led', 'delivered', 'achieved', 'improved', 'optimized'
            ]
        }
        
        # Red flags for unprofessional content
        self.red_flags = {
            'informal_language': [
                'gonna', 'wanna', 'gotta', 'kinda', 'sorta', 'yeah', 'nah',
                'awesome', 'cool', 'super', 'totally', 'really', 'pretty'
            ],
            'vague_language': [
                'stuff', 'things', 'whatever', 'somehow', 'maybe', 'probably',
                'basically', 'actually', 'literally', 'honestly'
            ],
            'weak_expressions': [
                'i think', 'i believe', 'i guess', 'i suppose', 'maybe i can',
                'i might be able to', 'i could try', 'hopefully'
            ]
        }
    
    def analyze_readability(self, text: str) -> Dict[str, float]:
        """Advanced readability analysis"""
        
        try:
            metrics = {
                'flesch_reading_ease': flesch_reading_ease(text),
                'automated_readability_index': automated_readability_index(text),
                'flesch_kincaid_grade': flesch_kincaid_grade(text),
                'avg_sentence_length': self._calculate_avg_sentence_length(text),
                'avg_word_length': self._calculate_avg_word_length(text)
            }
            
            # Calculate composite readability score
            readability_score = (
                metrics['flesch_reading_ease'] * 0.4 +
                max(0, 100 - metrics['flesch_kincaid_grade'] * 10) * 0.3 +
                max(0, 100 - metrics['automated_readability_index'] * 8) * 0.3
            )
            
            metrics['composite_score'] = max(0, min(100, readability_score))
            return metrics
            
        except Exception as e:
            logger.error(f"Error in readability analysis: {e}")
            return {'composite_score': 60.0}
    
    def _calculate_avg_sentence_length(self, text: str) -> float:
        """Calculate average sentence length"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0.0
        
        total_words = sum(len(s.split()) for s in sentences)
        return total_words / len(sentences)
    
    def _calculate_avg_word_length(self, text: str) -> float:
        """Calculate average word length"""
        words = text.split()
        if not words:
            return 0.0
        
        total_chars = sum(len(word.strip('.,!?;:')) for word in words)
        return total_chars / len(words)
    
    def analyze_professionalism(self, text: str) -> Dict[str, Any]:
        """Analyze professional tone and language"""
        
        analysis = {
            'score': 100.0,
            'issues': [],
            'strengths': [],
            'professional_indicators': 0,
            'red_flags': 0
        }
        
        text_lower = text.lower()
        
        # Check for professional vocabulary
        for category, words in self.professional_indicators.items():
            count = sum(1 for word in words if word in text_lower)
            analysis['professional_indicators'] += count
            
            if count > 0:
                analysis['strengths'].append(f"Uses {category.replace('_', ' ')}")
        
        # Check for red flags
        for category, phrases in self.red_flags.items():
            for phrase in phrases:
                if phrase in text_lower:
                    analysis['red_flags'] += 1
                    analysis['issues'].append(f"Unprofessional language: '{phrase}'")
                    analysis['score'] -= 10
        
        # Check for proper capitalization
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and not sentence[0].isupper():
                analysis['issues'].append("Improper sentence capitalization")
                analysis['score'] -= 5
        
        # Bonus for professional indicators
        analysis['score'] += min(20, analysis['professional_indicators'] * 2)
        
        analysis['score'] = max(0, min(100, analysis['score']))
        return analysis
    
    def analyze_personalization(self, text: str, job_description: str, 
                              company_info: Optional[str] = None) -> Dict[str, Any]:
        """Analyze how well the text is personalized"""
        
        analysis = {
            'score': 50.0,
            'personalization_elements': [],
            'generic_indicators': [],
            'company_mentions': 0,
            'job_specific_mentions': 0
        }
        
        text_lower = text.lower()
        job_lower = job_description.lower()
        
        # Check for company mentions
        if company_info:
            company_name = company_info.split('.')[0].strip()
            if company_name.lower() in text_lower:
                analysis['company_mentions'] += 1
                analysis['personalization_elements'].append(f"Mentions company: {company_name}")
                analysis['score'] += 15
        
        # Check for job-specific keywords
        job_keywords = self._extract_keywords(job_description)
        for keyword in job_keywords[:10]:  # Top 10 keywords
            if keyword.lower() in text_lower:
                analysis['job_specific_mentions'] += 1
                analysis['personalization_elements'].append(f"Uses job keyword: {keyword}")
                analysis['score'] += 5
        
        # Check for generic phrases (negative scoring)
        generic_phrases = [
            'dear hiring manager', 'to whom it may concern', 'i am writing to apply',
            'i am interested in this position', 'i would like to apply',
            'please consider my application', 'i am a perfect fit'
        ]
        
        for phrase in generic_phrases:
            if phrase in text_lower:
                analysis['generic_indicators'].append(phrase)
                analysis['score'] -= 10
        
        # Check for specific examples
        if 'example' in text_lower or 'for instance' in text_lower:
            analysis['personalization_elements'].append("Includes specific examples")
            analysis['score'] += 10
        
        # Check for research indicators
        research_indicators = ['i noticed', 'i saw', 'i researched', 'i found', 'i discovered']
        for indicator in research_indicators:
            if indicator in text_lower:
                analysis['personalization_elements'].append("Shows research effort")
                analysis['score'] += 8
                break
        
        analysis['score'] = max(0, min(100, analysis['score']))
        return analysis
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        try:
            if self.nlp:
                doc = self.nlp(text)
                keywords = [token.lemma_.lower() for token in doc 
                          if token.pos_ in ['NOUN', 'ADJ', 'VERB'] and 
                          not token.is_stop and token.is_alpha and len(token.text) > 2]
            else:
                # Fallback to simple keyword extraction
                words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
                keywords = [word for word in words if word not in self._get_stop_words()]
            
            return list(Counter(keywords).keys())[:20]
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    def _get_stop_words(self) -> set:
        """Get stop words"""
        try:
            from nltk.corpus import stopwords
            return set(stopwords.words('english'))
        except:
            return {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    
    def analyze_structure(self, text: str) -> Dict[str, Any]:
        """Analyze text structure and organization"""
        
        analysis = {
            'score': 70.0,
            'strengths': [],
            'weaknesses': [],
            'structure_elements': {}
        }
        
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Analyze paragraph structure
        if len(paragraphs) >= 3:
            analysis['strengths'].append("Good paragraph structure")
            analysis['score'] += 10
        elif len(paragraphs) == 1:
            analysis['weaknesses'].append("Single paragraph - needs structure")
            analysis['score'] -= 15
        
        # Check for introduction and conclusion
        if paragraphs:
            first_para = paragraphs[0].lower()
            last_para = paragraphs[-1].lower()
            
            # Introduction indicators
            intro_words = ['dear', 'hello', 'greetings', 'i am writing', 'i am interested']
            if any(word in first_para for word in intro_words):
                analysis['strengths'].append("Has clear introduction")
                analysis['score'] += 5
            
            # Conclusion indicators
            conclusion_words = ['thank you', 'looking forward', 'best regards', 'sincerely']
            if any(word in last_para for word in conclusion_words):
                analysis['strengths'].append("Has professional conclusion")
                analysis['score'] += 5
        
        # Analyze sentence variety
        sentence_lengths = [len(s.split()) for s in sentences]
        if sentence_lengths:
            avg_length = statistics.mean(sentence_lengths)
            std_dev = statistics.stdev(sentence_lengths) if len(sentence_lengths) > 1 else 0
            
            if std_dev > 5:
                analysis['strengths'].append("Good sentence variety")
                analysis['score'] += 5
            elif std_dev < 2:
                analysis['weaknesses'].append("Monotonous sentence structure")
                analysis['score'] -= 5
        
        # Check for bullet points or lists
        if '•' in text or re.search(r'^\d+\.', text, re.MULTILINE):
            analysis['strengths'].append("Uses structured lists")
            analysis['score'] += 8
        
        analysis['structure_elements'] = {
            'paragraph_count': len(paragraphs),
            'sentence_count': len(sentences),
            'avg_sentence_length': statistics.mean(sentence_lengths) if sentence_lengths else 0
        }
        
        analysis['score'] = max(0, min(100, analysis['score']))
        return analysis
    
    def analyze_technical_accuracy(self, text: str, job_description: str) -> Dict[str, Any]:
        """Analyze technical accuracy and terminology"""
        
        analysis = {
            'score': 80.0,
            'technical_terms': [],
            'accuracy_issues': [],
            'domain_expertise': []
        }
        
        # Extract technical terms from job description
        tech_patterns = [
            r'\b[A-Z]{2,}\b',  # Acronyms
            r'\b\w+\.\w+\b',   # File extensions, frameworks
            r'\b\w+(?:Script|SQL|API|SDK|IDE|DB)\b',  # Tech suffixes
        ]
        
        job_tech_terms = set()
        for pattern in tech_patterns:
            matches = re.findall(pattern, job_description)
            job_tech_terms.update(matches)
        
        # Check if technical terms are used correctly in the proposal
        text_tech_terms = set()
        for pattern in tech_patterns:
            matches = re.findall(pattern, text)
            text_tech_terms.update(matches)
        
        # Score based on technical term usage
        common_terms = job_tech_terms.intersection(text_tech_terms)
        if common_terms:
            analysis['technical_terms'] = list(common_terms)
            analysis['score'] += len(common_terms) * 3
            analysis['domain_expertise'].append(f"Uses relevant technical terms: {', '.join(list(common_terms)[:3])}")
        
        # Check for technical explanations
        explanation_indicators = [
            'implement', 'develop', 'integrate', 'optimize', 'configure',
            'architecture', 'framework', 'methodology', 'approach'
        ]
        
        found_explanations = [word for word in explanation_indicators if word in text.lower()]
        if found_explanations:
            analysis['domain_expertise'].append("Demonstrates technical understanding")
            analysis['score'] += 10
        
        analysis['score'] = max(0, min(100, analysis['score']))
        return analysis

class AdvancedQualityAssurance:
    """Advanced quality assurance system"""
    
    def __init__(self):
        self.config = get_config()
        self.text_analyzer = AdvancedTextAnalyzer()
        
        # Quality dimension weights
        self.dimension_weights = {
            QualityDimension.READABILITY: 0.12,
            QualityDimension.PROFESSIONALISM: 0.18,
            QualityDimension.PERSONALIZATION: 0.20,
            QualityDimension.TECHNICAL_ACCURACY: 0.15,
            QualityDimension.STRUCTURE: 0.12,
            QualityDimension.RELEVANCE: 0.10,
            QualityDimension.COMPLETENESS: 0.08,
            QualityDimension.TONE_CONSISTENCY: 0.05
        }
    
    @with_retry(operation_name="comprehensive_quality_assessment")
    async def comprehensive_quality_assessment(self, text: str, job_description: str,
                                             profile: str, company_info: Optional[str] = None) -> QualityAssessment:
        """Perform comprehensive quality assessment"""
        
        with TimedOperation("comprehensive_quality_assessment"):
            metrics = []
            all_issues = []
            
            # 1. Readability Analysis
            readability_data = self.text_analyzer.analyze_readability(text)
            readability_metric = QualityMetric(
                dimension=QualityDimension.READABILITY,
                score=readability_data['composite_score'],
                level=self._score_to_level(readability_data['composite_score']),
                weight=self.dimension_weights[QualityDimension.READABILITY],
                details=f"Flesch Reading Ease: {readability_data.get('flesch_reading_ease', 0):.1f}",
                recommendations=self._get_readability_recommendations(readability_data)
            )
            metrics.append(readability_metric)
            
            # 2. Professionalism Analysis
            professionalism_data = self.text_analyzer.analyze_professionalism(text)
            professionalism_metric = QualityMetric(
                dimension=QualityDimension.PROFESSIONALISM,
                score=professionalism_data['score'],
                level=self._score_to_level(professionalism_data['score']),
                weight=self.dimension_weights[QualityDimension.PROFESSIONALISM],
                details=f"Professional indicators: {professionalism_data['professional_indicators']}, Red flags: {professionalism_data['red_flags']}",
                recommendations=self._get_professionalism_recommendations(professionalism_data)
            )
            metrics.append(professionalism_metric)
            
            # Add issues from professionalism analysis
            for issue_msg in professionalism_data['issues']:
                all_issues.append(ValidationIssue(
                    type="professionalism",
                    severity=ValidationSeverity.WARNING,
                    message=issue_msg,
                    suggestion="Use more professional language"
                ))
            
            # 3. Personalization Analysis
            personalization_data = self.text_analyzer.analyze_personalization(text, job_description, company_info)
            personalization_metric = QualityMetric(
                dimension=QualityDimension.PERSONALIZATION,
                score=personalization_data['score'],
                level=self._score_to_level(personalization_data['score']),
                weight=self.dimension_weights[QualityDimension.PERSONALIZATION],
                details=f"Company mentions: {personalization_data['company_mentions']}, Job-specific mentions: {personalization_data['job_specific_mentions']}",
                recommendations=self._get_personalization_recommendations(personalization_data)
            )
            metrics.append(personalization_metric)
            
            # 4. Technical Accuracy Analysis
            technical_data = self.text_analyzer.analyze_technical_accuracy(text, job_description)
            technical_metric = QualityMetric(
                dimension=QualityDimension.TECHNICAL_ACCURACY,
                score=technical_data['score'],
                level=self._score_to_level(technical_data['score']),
                weight=self.dimension_weights[QualityDimension.TECHNICAL_ACCURACY],
                details=f"Technical terms used: {len(technical_data['technical_terms'])}",
                recommendations=self._get_technical_recommendations(technical_data)
            )
            metrics.append(technical_metric)
            
            # 5. Structure Analysis
            structure_data = self.text_analyzer.analyze_structure(text)
            structure_metric = QualityMetric(
                dimension=QualityDimension.STRUCTURE,
                score=structure_data['score'],
                level=self._score_to_level(structure_data['score']),
                weight=self.dimension_weights[QualityDimension.STRUCTURE],
                details=f"Paragraphs: {structure_data['structure_elements']['paragraph_count']}, Sentences: {structure_data['structure_elements']['sentence_count']}",
                recommendations=self._get_structure_recommendations(structure_data)
            )
            metrics.append(structure_metric)
            
            # 6. AI-Enhanced Analysis
            ai_analysis = await self._ai_enhanced_analysis(text, job_description, profile)
            
            # Calculate overall score
            overall_score = sum(metric.score * metric.weight for metric in metrics)
            
            # Generate comprehensive recommendations
            recommendations = self._generate_comprehensive_recommendations(metrics, ai_analysis)
            
            # Identify strengths and improvement areas
            strengths = self._identify_strengths(metrics)
            improvement_areas = self._identify_improvement_areas(metrics)
            
            # Calculate confidence score
            confidence = self._calculate_confidence(metrics, len(all_issues))
            
            assessment = QualityAssessment(
                overall_score=overall_score,
                overall_level=self._score_to_level(overall_score),
                metrics=metrics,
                issues=all_issues,
                recommendations=recommendations,
                strengths=strengths,
                improvement_areas=improvement_areas,
                confidence=confidence,
                assessment_timestamp=datetime.now()
            )
            
            logger.info(f"Comprehensive quality assessment completed: {overall_score:.1f}/100 ({assessment.overall_level.value})")
            return assessment
    
    def _score_to_level(self, score: float) -> QualityLevel:
        """Convert score to quality level"""
        if score >= 90:
            return QualityLevel.EXCELLENT
        elif score >= 75:
            return QualityLevel.GOOD
        elif score >= 60:
            return QualityLevel.FAIR
        else:
            return QualityLevel.POOR
    
    def _get_readability_recommendations(self, data: Dict[str, Any]) -> List[str]:
        """Generate readability recommendations"""
        recommendations = []
        
        if data['composite_score'] < 60:
            recommendations.append("Simplify sentence structure for better readability")
        
        if data.get('avg_sentence_length', 0) > 25:
            recommendations.append("Break down long sentences into shorter ones")
        
        if data.get('flesch_kincaid_grade', 0) > 12:
            recommendations.append("Use simpler vocabulary for broader accessibility")
        
        return recommendations
    
    def _get_professionalism_recommendations(self, data: Dict[str, Any]) -> List[str]:
        """Generate professionalism recommendations"""
        recommendations = []
        
        if data['red_flags'] > 0:
            recommendations.append("Replace informal language with professional alternatives")
        
        if data['professional_indicators'] < 3:
            recommendations.append("Include more professional vocabulary and business terms")
        
        return recommendations
    
    def _get_personalization_recommendations(self, data: Dict[str, Any]) -> List[str]:
        """Generate personalization recommendations"""
        recommendations = []
        
        if data['company_mentions'] == 0:
            recommendations.append("Mention the company name and show research")
        
        if data['job_specific_mentions'] < 3:
            recommendations.append("Include more job-specific keywords and requirements")
        
        if len(data['generic_indicators']) > 0:
            recommendations.append("Remove generic phrases and add specific details")
        
        return recommendations
    
    def _get_technical_recommendations(self, data: Dict[str, Any]) -> List[str]:
        """Generate technical accuracy recommendations"""
        recommendations = []
        
        if len(data['technical_terms']) < 2:
            recommendations.append("Include more relevant technical terms from the job description")
        
        if len(data['domain_expertise']) == 0:
            recommendations.append("Demonstrate technical understanding with specific examples")
        
        return recommendations
    
    def _get_structure_recommendations(self, data: Dict[str, Any]) -> List[str]:
        """Generate structure recommendations"""
        recommendations = []
        
        if data['structure_elements']['paragraph_count'] < 3:
            recommendations.append("Organize content into clear paragraphs")
        
        if 'Has clear introduction' not in data['strengths']:
            recommendations.append("Add a strong opening paragraph")
        
        if 'Has professional conclusion' not in data['strengths']:
            recommendations.append("Include a compelling closing statement")
        
        return recommendations
    
    async def _ai_enhanced_analysis(self, text: str, job_description: str, profile: str) -> Dict[str, Any]:
        """AI-enhanced quality analysis"""
        
        try:
            analysis_prompt = f"""
            Analyze this cover letter for quality and provide specific feedback:
            
            Job Description: {job_description[:800]}
            Freelancer Profile: {profile[:600]}
            Cover Letter: {text}
            
            Evaluate:
            1. Relevance to job requirements
            2. Demonstration of qualifications
            3. Persuasiveness and impact
            4. Completeness of response
            5. Professional presentation
            
            Return JSON with:
            {{
                "relevance_score": <0-100>,
                "qualification_demonstration": <0-100>,
                "persuasiveness": <0-100>,
                "completeness": <0-100>,
                "presentation": <0-100>,
                "key_strengths": ["strength1", "strength2"],
                "improvement_areas": ["area1", "area2"],
                "specific_feedback": "detailed feedback"
            }}
            """
            
            response = await ainvoke_llm(
                system_prompt="You are an expert proposal evaluator. Provide detailed, actionable feedback on cover letter quality.",
                user_message=analysis_prompt,
                model=self.config.llm.default_model
            )
            
            return json.loads(response)
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {
                "relevance_score": 70,
                "qualification_demonstration": 70,
                "persuasiveness": 70,
                "completeness": 70,
                "presentation": 70,
                "key_strengths": [],
                "improvement_areas": [],
                "specific_feedback": "AI analysis unavailable"
            }
    
    def _generate_comprehensive_recommendations(self, metrics: List[QualityMetric], ai_analysis: Dict[str, Any]) -> List[str]:
        """Generate comprehensive recommendations"""
        recommendations = []
        
        # Collect all metric recommendations
        for metric in metrics:
            recommendations.extend(metric.recommendations)
        
        # Add AI recommendations
        if ai_analysis.get('improvement_areas'):
            recommendations.extend([f"AI Insight: {area}" for area in ai_analysis['improvement_areas']])
        
        # Add specific feedback
        if ai_analysis.get('specific_feedback'):
            recommendations.append(f"Expert Feedback: {ai_analysis['specific_feedback']}")
        
        # Remove duplicates and limit to top 10
        unique_recommendations = list(dict.fromkeys(recommendations))
        return unique_recommendations[:10]
    
    def _identify_strengths(self, metrics: List[QualityMetric]) -> List[str]:
        """Identify key strengths"""
        strengths = []
        
        for metric in metrics:
            if metric.score >= 85:
                strengths.append(f"Excellent {metric.dimension.value.replace('_', ' ')}")
            elif metric.score >= 75:
                strengths.append(f"Good {metric.dimension.value.replace('_', ' ')}")
        
        return strengths
    
    def _identify_improvement_areas(self, metrics: List[QualityMetric]) -> List[str]:
        """Identify improvement areas"""
        improvement_areas = []
        
        for metric in metrics:
            if metric.score < 60:
                improvement_areas.append(f"Needs improvement: {metric.dimension.value.replace('_', ' ')}")
            elif metric.score < 75:
                improvement_areas.append(f"Could enhance: {metric.dimension.value.replace('_', ' ')}")
        
        return improvement_areas
    
    def _calculate_confidence(self, metrics: List[QualityMetric], issue_count: int) -> float:
        """Calculate confidence in assessment"""
        
        # Base confidence
        confidence = 85.0
        
        # Reduce confidence for missing dimensions
        if len(metrics) < 5:
            confidence -= 10
        
        # Reduce confidence for many issues
        confidence -= min(20, issue_count * 3)
        
        # Increase confidence for consistent scores
        scores = [metric.score for metric in metrics]
        if scores:
            score_variance = statistics.variance(scores)
            if score_variance < 100:  # Low variance means consistent assessment
                confidence += 5
        
        return max(50, min(100, confidence))

# Global advanced quality assurance instance
advanced_quality_assurance = AdvancedQualityAssurance()

# Convenience functions
async def comprehensive_quality_assessment(text: str, job_description: str, profile: str, company_info: Optional[str] = None) -> QualityAssessment:
    """Perform comprehensive quality assessment"""
    return await advanced_quality_assurance.comprehensive_quality_assessment(text, job_description, profile, company_info)

def quality_score_to_recommendation(score: float) -> str:
    """Convert quality score to action recommendation"""
    if score >= 90:
        return "Excellent quality - ready to submit"
    elif score >= 80:
        return "Good quality - minor improvements suggested"
    elif score >= 70:
        return "Fair quality - review recommendations"
    elif score >= 60:
        return "Poor quality - significant improvements needed"
    else:
        return "Critical quality issues - major revision required"