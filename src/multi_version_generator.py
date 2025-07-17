import json
import asyncio
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import uuid

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config
from .utils import ainvoke_llm
from .database import get_database_manager
from .client_intelligence import ClientAnalysisResult
from .enhanced_scoring import ScoringResult
from .dynamic_personalization import PersonalizationContext

class ContentVersion(Enum):
    """Content version types for A/B testing"""
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    TECHNICAL = "technical"
    BUSINESS = "business"

class ContentTone(Enum):
    """Content tone variations"""
    PROFESSIONAL = "professional"
    CONVERSATIONAL = "conversational"
    CONSULTATIVE = "consultative"
    CONFIDENT = "confident"
    COLLABORATIVE = "collaborative"

class ContentStrategy(Enum):
    """Content strategy approaches"""
    PROBLEM_SOLUTION = "problem_solution"
    EXPERIENCE_FOCUSED = "experience_focused"
    RESULT_DRIVEN = "result_driven"
    RELATIONSHIP_BUILDING = "relationship_building"
    VALUE_PROPOSITION = "value_proposition"

@dataclass
class ContentVariation:
    """Represents a content variation for A/B testing"""
    variation_id: str
    version: ContentVersion
    tone: ContentTone
    strategy: ContentStrategy
    content: str
    word_count: int
    key_elements: List[str]
    personalization_score: float
    technical_depth: str
    business_focus: str
    generated_at: datetime

@dataclass
class MultiVersionResult:
    """Result of multi-version content generation"""
    job_id: str
    primary_version: ContentVariation
    alternative_versions: List[ContentVariation]
    performance_predictions: Dict[str, float]
    recommended_version: str
    ab_test_ready: bool
    generation_metadata: Dict[str, Any]

@dataclass
class VersionPerformance:
    """Track performance of content versions"""
    variation_id: str
    version: ContentVersion
    applications_sent: int
    responses_received: int
    interviews_scheduled: int
    projects_won: int
    response_rate: float
    interview_rate: float
    win_rate: float
    average_response_time: float
    client_feedback_score: float
    last_updated: datetime

class ContentStrategyEngine:
    """Engine for generating different content strategies"""
    
    def __init__(self):
        self.config = get_config()
        
    async def generate_strategy_variations(self, job_data: Dict[str, Any], 
                                         client_analysis: ClientAnalysisResult,
                                         scoring_result: ScoringResult,
                                         personalization_context: PersonalizationContext) -> List[ContentStrategy]:
        """Generate appropriate content strategies based on job and client analysis"""
        
        strategies = []
        
        # Analyze job requirements to determine best strategies
        job_description = job_data.get('description', '').lower()
        client_type = client_analysis.client_profile.risk_level
        
        # Always include balanced approach
        strategies.append(ContentStrategy.PROBLEM_SOLUTION)
        
        # Add strategies based on job type
        if any(keyword in job_description for keyword in ['technical', 'development', 'programming', 'coding']):
            strategies.append(ContentStrategy.EXPERIENCE_FOCUSED)
        
        if any(keyword in job_description for keyword in ['results', 'performance', 'growth', 'roi']):
            strategies.append(ContentStrategy.RESULT_DRIVEN)
        
        if any(keyword in job_description for keyword in ['partnership', 'collaboration', 'team', 'long-term']):
            strategies.append(ContentStrategy.RELATIONSHIP_BUILDING)
        
        # Add value proposition for high-budget clients
        if scoring_result.factors.budget_alignment > 70:
            strategies.append(ContentStrategy.VALUE_PROPOSITION)
        
        # Limit to top 3 strategies
        return strategies[:3]
    
    async def generate_tone_variations(self, client_analysis: ClientAnalysisResult,
                                     job_data: Dict[str, Any]) -> List[ContentTone]:
        """Generate appropriate tone variations based on client and job"""
        
        tones = []
        client_type = client_analysis.client_profile.risk_level
        
        # Default professional tone
        tones.append(ContentTone.PROFESSIONAL)
        
        # Add conversational for individual clients or creative jobs
        job_description = job_data.get('description', '').lower()
        if 'creative' in job_description or 'startup' in job_description:
            tones.append(ContentTone.CONVERSATIONAL)
        
        # Add consultative for complex projects
        if len(job_data.get('description', '')) > 1000:
            tones.append(ContentTone.CONSULTATIVE)
        
        # Add confident for high-value projects
        if client_analysis.client_profile.avg_project_value > 5000:
            tones.append(ContentTone.CONFIDENT)
        
        return tones[:2]  # Limit to 2 tone variations

class VersionGenerator:
    """Generates multiple versions of content for A/B testing"""
    
    def __init__(self):
        self.config = get_config()
        self.strategy_engine = ContentStrategyEngine()
        self.db_manager = get_database_manager()
        
    @with_retry(operation_name="generate_content_versions")
    async def generate_multiple_versions(self, job_data: Dict[str, Any],
                                       client_analysis: ClientAnalysisResult,
                                       scoring_result: ScoringResult,
                                       personalization_context: PersonalizationContext,
                                       profile: str) -> MultiVersionResult:
        """Generate multiple content versions for A/B testing"""
        
        with TimedOperation("multi_version_generation"):
            job_id = job_data.get('job_id', str(uuid.uuid4()))
            
            # Get strategic variations
            strategies = await self.strategy_engine.generate_strategy_variations(
                job_data, client_analysis, scoring_result, personalization_context
            )
            
            tones = await self.strategy_engine.generate_tone_variations(
                client_analysis, job_data
            )
            
            # Generate content variations
            variations = []
            
            # Create combinations of strategies and tones
            for strategy in strategies:
                for tone in tones:
                    variation = await self._generate_single_variation(
                        job_data, client_analysis, scoring_result, 
                        personalization_context, profile, strategy, tone
                    )
                    variations.append(variation)
            
            # Select primary version (usually the first/best combination)
            primary_version = variations[0]
            alternative_versions = variations[1:]
            
            # Predict performance for each version
            performance_predictions = {}
            for variation in variations:
                prediction = await self._predict_version_performance(
                    variation, job_data, client_analysis, scoring_result
                )
                performance_predictions[variation.variation_id] = prediction
            
            # Recommend best version based on predictions
            recommended_version = max(performance_predictions, key=performance_predictions.get)
            
            # Check if ready for A/B testing
            ab_test_ready = len(variations) >= 2 and len(set(v.version for v in variations)) >= 2
            
            result = MultiVersionResult(
                job_id=job_id,
                primary_version=primary_version,
                alternative_versions=alternative_versions,
                performance_predictions=performance_predictions,
                recommended_version=recommended_version,
                ab_test_ready=ab_test_ready,
                generation_metadata={
                    'strategies_used': [s.value for s in strategies],
                    'tones_used': [t.value for t in tones],
                    'total_variations': len(variations),
                    'generated_at': datetime.now().isoformat()
                }
            )
            
            # Store in database for tracking
            await self._store_version_results(result)
            
            logger.info(f"Generated {len(variations)} content versions for job {job_id}")
            return result
    
    async def _generate_single_variation(self, job_data: Dict[str, Any],
                                       client_analysis: ClientAnalysisResult,
                                       scoring_result: ScoringResult,
                                       personalization_context: PersonalizationContext,
                                       profile: str,
                                       strategy: ContentStrategy,
                                       tone: ContentTone) -> ContentVariation:
        """Generate a single content variation"""
        
        # Determine version type based on strategy and tone
        version = self._determine_version_type(strategy, tone)
        
        # Create variation-specific prompt
        prompt = self._create_variation_prompt(
            job_data, client_analysis, scoring_result, 
            personalization_context, profile, strategy, tone, version
        )
        
        # Generate content
        content = await ainvoke_llm(
            system_prompt=self._get_system_prompt_for_variation(version, strategy, tone),
            user_message=prompt,
            model=self.config.llm.default_model
        )
        
        # Analyze generated content
        word_count = len(content.split())
        key_elements = self._extract_key_elements(content, strategy)
        personalization_score = self._calculate_personalization_score(content, personalization_context)
        technical_depth = self._assess_technical_depth(content)
        business_focus = self._assess_business_focus(content)
        
        variation_id = str(uuid.uuid4())
        
        return ContentVariation(
            variation_id=variation_id,
            version=version,
            tone=tone,
            strategy=strategy,
            content=content,
            word_count=word_count,
            key_elements=key_elements,
            personalization_score=personalization_score,
            technical_depth=technical_depth,
            business_focus=business_focus,
            generated_at=datetime.now()
        )
    
    def _determine_version_type(self, strategy: ContentStrategy, tone: ContentTone) -> ContentVersion:
        """Determine version type based on strategy and tone combination"""
        
        if strategy == ContentStrategy.RESULT_DRIVEN and tone == ContentTone.CONFIDENT:
            return ContentVersion.AGGRESSIVE
        elif strategy == ContentStrategy.EXPERIENCE_FOCUSED and tone == ContentTone.PROFESSIONAL:
            return ContentVersion.TECHNICAL
        elif strategy == ContentStrategy.VALUE_PROPOSITION and tone == ContentTone.CONSULTATIVE:
            return ContentVersion.BUSINESS
        elif strategy == ContentStrategy.RELATIONSHIP_BUILDING:
            return ContentVersion.CONSERVATIVE
        else:
            return ContentVersion.BALANCED
    
    def _create_variation_prompt(self, job_data: Dict[str, Any],
                               client_analysis: ClientAnalysisResult,
                               scoring_result: ScoringResult,
                               personalization_context: PersonalizationContext,
                               profile: str,
                               strategy: ContentStrategy,
                               tone: ContentTone,
                               version: ContentVersion) -> str:
        """Create variation-specific prompt"""
        
        strategy_instructions = {
            ContentStrategy.PROBLEM_SOLUTION: "Focus on identifying the client's problem and presenting your solution clearly.",
            ContentStrategy.EXPERIENCE_FOCUSED: "Emphasize your relevant experience and past project successes.",
            ContentStrategy.RESULT_DRIVEN: "Highlight specific results and measurable outcomes you've achieved.",
            ContentStrategy.RELATIONSHIP_BUILDING: "Focus on building rapport and long-term partnership potential.",
            ContentStrategy.VALUE_PROPOSITION: "Clearly articulate the unique value you bring to the project."
        }
        
        tone_instructions = {
            ContentTone.PROFESSIONAL: "Use formal, professional language with proper business etiquette.",
            ContentTone.CONVERSATIONAL: "Use a friendly, approachable tone that feels natural and engaging.",
            ContentTone.CONSULTATIVE: "Position yourself as an expert advisor offering strategic insights.",
            ContentTone.CONFIDENT: "Use assertive language that demonstrates expertise and capability.",
            ContentTone.COLLABORATIVE: "Emphasize teamwork and partnership throughout the message."
        }
        
        return f"""
        Generate a {version.value} cover letter for this Upwork job using the {strategy.value} strategy with a {tone.value} tone.

        Job Details:
        Title: {job_data.get('title', 'Unknown')}
        Description: {job_data.get('description', '')[:1000]}
        Budget: {job_data.get('payment_rate', 'Not specified')}
        Experience Level: {job_data.get('experience_level', 'Not specified')}

        Client Analysis:
        - Success Probability: {client_analysis.client_profile.success_probability:.1f}%
        - Risk Level: {client_analysis.client_profile.risk_level.value}
        - Communication Quality: {client_analysis.client_profile.communication_quality:.1f}%
        - Average Project Value: ${client_analysis.client_profile.avg_project_value:.2f}

        Personalization Context:
        Company: {personalization_context.company_research.company_name}
        Industry: {personalization_context.company_research.industry}
        Key Insights: {', '.join(personalization_context.company_research.key_insights[:3])}

        Freelancer Profile:
        {profile[:800]}

        Strategy Instructions: {strategy_instructions[strategy]}
        Tone Instructions: {tone_instructions[tone]}

        Requirements:
        - Target word count: {self.config.cover_letter.target_word_count}
        - Include specific examples relevant to the job
        - Mention the company name and show you've researched them
        - Include a clear call to action
        - Ensure the content matches the specified strategy and tone exactly
        """
    
    def _get_system_prompt_for_variation(self, version: ContentVersion, 
                                       strategy: ContentStrategy, 
                                       tone: ContentTone) -> str:
        """Get system prompt for specific variation"""
        
        return f"""
        You are an expert freelance proposal writer specialized in creating {version.value} proposals.
        
        Your task is to create a compelling cover letter that:
        1. Uses the {strategy.value} strategy effectively
        2. Maintains a {tone.value} tone throughout
        3. Demonstrates deep understanding of the client's needs
        4. Positions the freelancer as the ideal candidate
        5. Includes specific, relevant examples
        6. Has a clear structure and flow
        7. Ends with a strong call to action
        
        Key principles:
        - Be specific and avoid generic statements
        - Show don't tell - use concrete examples
        - Address the client's pain points directly
        - Demonstrate value proposition clearly
        - Use professional formatting and structure
        
        Return only the cover letter content without any additional commentary.
        """
    
    def _extract_key_elements(self, content: str, strategy: ContentStrategy) -> List[str]:
        """Extract key elements from generated content"""
        elements = []
        
        # Check for specific strategy elements
        if strategy == ContentStrategy.PROBLEM_SOLUTION:
            if "problem" in content.lower() or "challenge" in content.lower():
                elements.append("problem_identification")
            if "solution" in content.lower() or "solve" in content.lower():
                elements.append("solution_presentation")
        
        # Check for common elements
        if "experience" in content.lower() or "worked" in content.lower():
            elements.append("experience_mention")
        
        if any(word in content.lower() for word in ["result", "increased", "improved", "delivered"]):
            elements.append("results_focused")
        
        if "portfolio" in content.lower() or "example" in content.lower():
            elements.append("portfolio_reference")
        
        if "?" in content:
            elements.append("questions_asked")
        
        if "discuss" in content.lower() or "chat" in content.lower():
            elements.append("call_to_action")
        
        return elements
    
    def _calculate_personalization_score(self, content: str, 
                                       personalization_context: PersonalizationContext) -> float:
        """Calculate how personalized the content is"""
        score = 0
        
        # Check for company name mention
        if personalization_context.company_research.company_name.lower() in content.lower():
            score += 25
        
        # Check for industry mention
        if personalization_context.company_research.industry.lower() in content.lower():
            score += 20
        
        # Check for key insights
        for insight in personalization_context.company_research.key_insights:
            if any(word in content.lower() for word in insight.lower().split()[:3]):
                score += 15
                break
        
        # Check for specific details
        if len(content.split()) > 150:  # Detailed content
            score += 20
        
        # Check for tailored approach
        if any(word in content.lower() for word in ["specifically", "particularly", "unique", "tailored"]):
            score += 20
        
        return min(100, score)
    
    def _assess_technical_depth(self, content: str) -> str:
        """Assess technical depth of content"""
        technical_keywords = ['technical', 'implementation', 'architecture', 'system', 'code', 'development']
        
        technical_count = sum(1 for keyword in technical_keywords if keyword in content.lower())
        
        if technical_count >= 3:
            return "high"
        elif technical_count >= 1:
            return "medium"
        else:
            return "low"
    
    def _assess_business_focus(self, content: str) -> str:
        """Assess business focus of content"""
        business_keywords = ['business', 'roi', 'revenue', 'growth', 'strategy', 'objectives', 'goals']
        
        business_count = sum(1 for keyword in business_keywords if keyword in content.lower())
        
        if business_count >= 3:
            return "high"
        elif business_count >= 1:
            return "medium"
        else:
            return "low"
    
    async def _predict_version_performance(self, variation: ContentVariation,
                                         job_data: Dict[str, Any],
                                         client_analysis: ClientAnalysisResult,
                                         scoring_result: ScoringResult) -> float:
        """Predict performance of a content variation"""
        
        # Base prediction on historical data if available
        historical_performance = await self._get_historical_performance(variation.version)
        
        # Adjust based on client analysis
        client_adjustment = client_analysis.client_profile.success_probability / 100
        
        # Adjust based on personalization score
        personalization_adjustment = variation.personalization_score / 100
        
        # Adjust based on job scoring
        job_adjustment = scoring_result.overall_score / 100
        
        # Calculate weighted prediction
        prediction = (
            historical_performance * 0.4 +
            client_adjustment * 0.3 +
            personalization_adjustment * 0.2 +
            job_adjustment * 0.1
        ) * 100
        
        return min(100, max(0, prediction))
    
    async def _get_historical_performance(self, version: ContentVersion) -> float:
        """Get historical performance data for a version type"""
        try:
            # Query database for historical performance
            # This is a simplified version - real implementation would query actual data
            default_performance = {
                ContentVersion.CONSERVATIVE: 0.65,
                ContentVersion.AGGRESSIVE: 0.55,
                ContentVersion.BALANCED: 0.70,
                ContentVersion.TECHNICAL: 0.60,
                ContentVersion.BUSINESS: 0.75
            }
            
            return default_performance.get(version, 0.60)
            
        except Exception as e:
            logger.error(f"Error getting historical performance: {e}")
            return 0.60  # Default fallback
    
    async def _store_version_results(self, result: MultiVersionResult):
        """Store version results in database for tracking"""
        try:
            # Store in database for future analysis
            # This would typically involve inserting into a versions table
            logger.info(f"Stored version results for job {result.job_id}")
            
        except Exception as e:
            logger.error(f"Error storing version results: {e}")

class PerformanceTracker:
    """Tracks performance of different content versions"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        
    async def track_application_sent(self, variation_id: str):
        """Track when an application is sent"""
        # Update database with application sent event
        pass
    
    async def track_response_received(self, variation_id: str, response_time_hours: float):
        """Track when a response is received"""
        # Update database with response received event
        pass
    
    async def track_interview_scheduled(self, variation_id: str):
        """Track when an interview is scheduled"""
        # Update database with interview scheduled event
        pass
    
    async def track_project_won(self, variation_id: str):
        """Track when a project is won"""
        # Update database with project won event
        pass
    
    async def get_version_performance(self, version: ContentVersion) -> VersionPerformance:
        """Get performance statistics for a version type"""
        # Query database for performance statistics
        # Return aggregated performance data
        pass
    
    async def get_best_performing_version(self) -> ContentVersion:
        """Get the best performing version type"""
        # Analyze all version performances and return the best
        pass

# Global instances
version_generator = VersionGenerator()
performance_tracker = PerformanceTracker()

# Convenience functions
async def generate_content_versions(job_data: Dict[str, Any],
                                  client_analysis: ClientAnalysisResult,
                                  scoring_result: ScoringResult,
                                  personalization_context: PersonalizationContext,
                                  profile: str) -> MultiVersionResult:
    """Generate multiple content versions for A/B testing"""
    return await version_generator.generate_multiple_versions(
        job_data, client_analysis, scoring_result, personalization_context, profile
    )

async def track_version_performance(variation_id: str, event_type: str, **kwargs):
    """Track performance events for content versions"""
    if event_type == "application_sent":
        await performance_tracker.track_application_sent(variation_id)
    elif event_type == "response_received":
        await performance_tracker.track_response_received(variation_id, kwargs.get('response_time_hours', 0))
    elif event_type == "interview_scheduled":
        await performance_tracker.track_interview_scheduled(variation_id)
    elif event_type == "project_won":
        await performance_tracker.track_project_won(variation_id)