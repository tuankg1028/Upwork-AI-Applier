import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config
from .utils import ainvoke_llm
from .database import get_database_manager

class FollowUpTrigger(Enum):
    """Triggers for follow-up actions"""
    NO_RESPONSE = "no_response"
    VIEWED_NOT_RESPONDED = "viewed_not_responded"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    PROJECT_AWARDED = "project_awarded"
    PROJECT_DECLINED = "project_declined"
    CLIENT_QUESTION = "client_question"
    DEADLINE_APPROACHING = "deadline_approaching"

class FollowUpType(Enum):
    """Types of follow-up actions"""
    GENTLE_REMINDER = "gentle_reminder"
    VALUE_REINFORCEMENT = "value_reinforcement"
    ADDITIONAL_INFORMATION = "additional_information"
    THANK_YOU = "thank_you"
    STATUS_INQUIRY = "status_inquiry"
    PORTFOLIO_SHOWCASE = "portfolio_showcase"
    AVAILABILITY_UPDATE = "availability_update"
    RATE_NEGOTIATION = "rate_negotiation"

class FollowUpStatus(Enum):
    """Status of follow-up actions"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENT = "sent"
    RESPONDED = "responded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

@dataclass
class FollowUpAction:
    """Represents a follow-up action"""
    action_id: str
    job_id: str
    trigger: FollowUpTrigger
    followup_type: FollowUpType
    message: str
    scheduled_time: datetime
    status: FollowUpStatus
    priority: int
    metadata: Dict[str, Any]
    created_at: datetime
    sent_at: Optional[datetime] = None
    response_received: Optional[datetime] = None

@dataclass
class FollowUpStrategy:
    """Strategy for following up on applications"""
    job_id: str
    client_profile: str
    application_score: float
    timeline: List[FollowUpAction]
    total_actions: int
    estimated_success_rate: float
    strategy_notes: str

class FollowUpAnalyzer:
    """Analyzes applications and determines optimal follow-up strategies"""
    
    def __init__(self):
        self.config = get_config()
        self.db_manager = get_database_manager()
        
    async def analyze_followup_potential(self, job_data: Dict[str, Any],
                                       client_analysis: Any,
                                       application_data: Dict[str, Any]) -> float:
        """Analyze the potential success of follow-up actions"""
        
        try:
            # Base score from application quality
            base_score = application_data.get('quality_score', 70)
            
            # Adjust based on client characteristics
            client_score = client_analysis.client_profile.success_probability
            
            # Adjust based on job characteristics
            job_score = self._assess_job_followup_potential(job_data)
            
            # Calculate weighted potential
            potential = (
                base_score * 0.4 +
                client_score * 0.4 +
                job_score * 0.2
            )
            
            return min(100, max(0, potential))
            
        except Exception as e:
            logger.error(f"Error analyzing follow-up potential: {e}")
            return 60.0
    
    def _assess_job_followup_potential(self, job_data: Dict[str, Any]) -> float:
        """Assess job-specific follow-up potential"""
        
        score = 70.0
        description = job_data.get('description', '').lower()
        
        # Positive indicators
        if 'urgent' in description:
            score += 15  # Urgent jobs may need follow-up
        
        if 'long-term' in description or 'ongoing' in description:
            score += 10  # Long-term projects worth following up
        
        if 'budget' in description and '$' in description:
            score += 5  # Clear budget indicates serious client
        
        # Negative indicators
        if 'quick' in description and 'cheap' in description:
            score -= 15  # Low-quality job indicators
        
        if 'test' in description or 'trial' in description:
            score -= 10  # Test projects may not be worth following up
        
        return max(0, min(100, score))
    
    async def create_followup_strategy(self, job_data: Dict[str, Any],
                                     client_analysis: Any,
                                     application_data: Dict[str, Any]) -> FollowUpStrategy:
        """Create a comprehensive follow-up strategy"""
        
        with TimedOperation("followup_strategy_creation"):
            job_id = job_data.get('job_id', str(uuid.uuid4()))
            
            # Analyze follow-up potential
            potential = await self.analyze_followup_potential(job_data, client_analysis, application_data)
            
            # Create timeline based on potential and client type
            timeline = await self._create_followup_timeline(
                job_id, job_data, client_analysis, potential
            )
            
            # Generate strategy notes
            strategy_notes = await self._generate_strategy_notes(
                job_data, client_analysis, potential
            )
            
            strategy = FollowUpStrategy(
                job_id=job_id,
                client_profile=f"{client_analysis.client_profile.risk_level.value} risk, {client_analysis.client_profile.success_probability:.0f}% success rate",
                application_score=application_data.get('quality_score', 70),
                timeline=timeline,
                total_actions=len(timeline),
                estimated_success_rate=potential,
                strategy_notes=strategy_notes
            )
            
            logger.info(f"Created follow-up strategy for job {job_id}: {len(timeline)} actions, {potential:.1f}% success rate")
            return strategy
    
    async def _create_followup_timeline(self, job_id: str,
                                      job_data: Dict[str, Any],
                                      client_analysis: Any,
                                      potential: float) -> List[FollowUpAction]:
        """Create a timeline of follow-up actions"""
        
        timeline = []
        base_time = datetime.now()
        
        # Determine follow-up schedule based on client type and potential
        if potential > 80:
            # High potential - aggressive follow-up
            schedule = [
                (3, FollowUpType.GENTLE_REMINDER),
                (7, FollowUpType.VALUE_REINFORCEMENT),
                (14, FollowUpType.ADDITIONAL_INFORMATION),
                (21, FollowUpType.PORTFOLIO_SHOWCASE)
            ]
        elif potential > 60:
            # Medium potential - moderate follow-up
            schedule = [
                (5, FollowUpType.GENTLE_REMINDER),
                (12, FollowUpType.VALUE_REINFORCEMENT),
                (25, FollowUpType.STATUS_INQUIRY)
            ]
        else:
            # Low potential - minimal follow-up
            schedule = [
                (7, FollowUpType.GENTLE_REMINDER),
                (21, FollowUpType.STATUS_INQUIRY)
            ]
        
        # Create follow-up actions
        for days, followup_type in schedule:
            action = await self._create_followup_action(
                job_id, job_data, client_analysis, followup_type,
                base_time + timedelta(days=days)
            )
            timeline.append(action)
        
        return timeline
    
    async def _create_followup_action(self, job_id: str,
                                    job_data: Dict[str, Any],
                                    client_analysis: Any,
                                    followup_type: FollowUpType,
                                    scheduled_time: datetime) -> FollowUpAction:
        """Create a specific follow-up action"""
        
        # Generate message for this follow-up type
        message = await self._generate_followup_message(
            job_data, client_analysis, followup_type
        )
        
        # Determine priority
        priority = self._calculate_action_priority(followup_type, client_analysis)
        
        action = FollowUpAction(
            action_id=str(uuid.uuid4()),
            job_id=job_id,
            trigger=FollowUpTrigger.NO_RESPONSE,  # Default trigger
            followup_type=followup_type,
            message=message,
            scheduled_time=scheduled_time,
            status=FollowUpStatus.SCHEDULED,
            priority=priority,
            metadata={
                'client_type': client_analysis.client_profile.risk_level.value,
                'success_probability': client_analysis.client_profile.success_probability,
                'job_title': job_data.get('title', 'Unknown')
            },
            created_at=datetime.now()
        )
        
        return action
    
    async def _generate_followup_message(self, job_data: Dict[str, Any],
                                       client_analysis: Any,
                                       followup_type: FollowUpType) -> str:
        """Generate a follow-up message using AI"""
        
        try:
            message_prompt = f"""
            Generate a professional follow-up message for an Upwork job application:
            
            Job Title: {job_data.get('title', 'Unknown')}
            Job Description: {job_data.get('description', '')[:500]}
            Client Risk Level: {client_analysis.client_profile.risk_level.value}
            Client Success Rate: {client_analysis.client_profile.success_probability:.0f}%
            
            Follow-up Type: {followup_type.value}
            
            Message Requirements:
            - Professional and courteous tone
            - Specific to the job and client
            - Appropriate length (2-3 sentences)
            - Clear call to action
            - Avoid being pushy or desperate
            
            For {followup_type.value} type:
            {self._get_followup_type_guidance(followup_type)}
            
            Return only the message content, no additional text.
            """
            
            message = await ainvoke_llm(
                system_prompt="You are an expert at writing professional follow-up messages for freelance job applications.",
                user_message=message_prompt,
                model=self.config.llm.default_model
            )
            
            return message.strip()
            
        except Exception as e:
            logger.error(f"Error generating follow-up message: {e}")
            return self._get_fallback_message(followup_type)
    
    def _get_followup_type_guidance(self, followup_type: FollowUpType) -> str:
        """Get specific guidance for each follow-up type"""
        
        guidance = {
            FollowUpType.GENTLE_REMINDER: "Politely remind about your application and express continued interest.",
            FollowUpType.VALUE_REINFORCEMENT: "Reinforce your value proposition and highlight key qualifications.",
            FollowUpType.ADDITIONAL_INFORMATION: "Offer additional relevant information or portfolio examples.",
            FollowUpType.THANK_YOU: "Express gratitude and maintain professional relationship.",
            FollowUpType.STATUS_INQUIRY: "Politely inquire about the status of the application process.",
            FollowUpType.PORTFOLIO_SHOWCASE: "Share additional portfolio pieces or case studies.",
            FollowUpType.AVAILABILITY_UPDATE: "Update on your availability and capacity.",
            FollowUpType.RATE_NEGOTIATION: "Discuss rate flexibility or value justification."
        }
        
        return guidance.get(followup_type, "Create a professional follow-up message.")
    
    def _get_fallback_message(self, followup_type: FollowUpType) -> str:
        """Get fallback message for each follow-up type"""
        
        fallback_messages = {
            FollowUpType.GENTLE_REMINDER: "I wanted to follow up on my recent application for your project. I remain very interested and available to discuss how I can help achieve your goals.",
            FollowUpType.VALUE_REINFORCEMENT: "I wanted to highlight how my experience aligns perfectly with your project needs. I'm confident I can deliver exceptional results within your timeline.",
            FollowUpType.ADDITIONAL_INFORMATION: "I have some additional portfolio examples that might be relevant to your project. I'd be happy to share them if you're interested.",
            FollowUpType.STATUS_INQUIRY: "I hope you're doing well. I wanted to check on the status of your project and see if you need any additional information from me.",
            FollowUpType.PORTFOLIO_SHOWCASE: "I've completed some recent projects that demonstrate exactly the skills you're looking for. Would you like me to share these examples?",
            FollowUpType.AVAILABILITY_UPDATE: "I wanted to update you on my availability and confirm that I can prioritize your project if selected.",
            FollowUpType.RATE_NEGOTIATION: "I'm open to discussing the project scope and budget to find a solution that works for both of us."
        }
        
        return fallback_messages.get(followup_type, "Thank you for considering my application. I look forward to hearing from you.")
    
    def _calculate_action_priority(self, followup_type: FollowUpType, client_analysis: Any) -> int:
        """Calculate priority for follow-up action"""
        
        base_priority = {
            FollowUpType.GENTLE_REMINDER: 5,
            FollowUpType.VALUE_REINFORCEMENT: 7,
            FollowUpType.ADDITIONAL_INFORMATION: 6,
            FollowUpType.THANK_YOU: 3,
            FollowUpType.STATUS_INQUIRY: 4,
            FollowUpType.PORTFOLIO_SHOWCASE: 8,
            FollowUpType.AVAILABILITY_UPDATE: 5,
            FollowUpType.RATE_NEGOTIATION: 6
        }
        
        priority = base_priority.get(followup_type, 5)
        
        # Adjust based on client quality
        if client_analysis.client_profile.success_probability > 80:
            priority += 2
        elif client_analysis.client_profile.success_probability < 50:
            priority -= 1
        
        return max(1, min(10, priority))
    
    async def _generate_strategy_notes(self, job_data: Dict[str, Any],
                                     client_analysis: Any,
                                     potential: float) -> str:
        """Generate strategy notes for the follow-up plan"""
        
        notes = f"Follow-up Strategy Analysis:\n\n"
        
        # Client assessment
        notes += f"Client Assessment:\n"
        notes += f"- Risk Level: {client_analysis.client_profile.risk_level.value}\n"
        notes += f"- Success Probability: {client_analysis.client_profile.success_probability:.0f}%\n"
        notes += f"- Average Project Value: ${client_analysis.client_profile.avg_project_value:.2f}\n\n"
        
        # Strategy rationale
        notes += f"Strategy Rationale:\n"
        if potential > 80:
            notes += "- High potential client - aggressive follow-up strategy\n"
            notes += "- Multiple touchpoints to maintain engagement\n"
        elif potential > 60:
            notes += "- Medium potential client - balanced approach\n"
            notes += "- Moderate follow-up frequency\n"
        else:
            notes += "- Lower potential client - minimal follow-up\n"
            notes += "- Conservative approach to avoid over-engagement\n"
        
        # Recommendations
        notes += f"\nRecommendations:\n"
        if client_analysis.client_profile.communication_quality > 80:
            notes += "- Client shows good communication - expect responses\n"
        
        if client_analysis.client_profile.avg_project_value > 2000:
            notes += "- High-value projects - worth persistent follow-up\n"
        
        if 'urgent' in job_data.get('description', '').lower():
            notes += "- Urgent project - follow up more frequently\n"
        
        return notes

class FollowUpManager:
    """Manages follow-up actions and scheduling"""
    
    def __init__(self):
        self.config = get_config()
        self.db_manager = get_database_manager()
        self.analyzer = FollowUpAnalyzer()
        
    async def schedule_followup_strategy(self, job_data: Dict[str, Any],
                                       client_analysis: Any,
                                       application_data: Dict[str, Any]) -> FollowUpStrategy:
        """Schedule a complete follow-up strategy"""
        
        strategy = await self.analyzer.create_followup_strategy(
            job_data, client_analysis, application_data
        )
        
        # Store strategy in database
        await self._store_strategy(strategy)
        
        return strategy
    
    async def get_pending_followups(self, days_ahead: int = 7) -> List[FollowUpAction]:
        """Get pending follow-up actions for the next N days"""
        
        try:
            # This would query the database for pending actions
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Error getting pending follow-ups: {e}")
            return []
    
    async def execute_followup_action(self, action: FollowUpAction) -> bool:
        """Execute a specific follow-up action"""
        
        try:
            # In a real implementation, this would:
            # 1. Send the message through Upwork API
            # 2. Update the action status
            # 3. Log the action
            
            logger.info(f"Executing follow-up action: {action.followup_type.value} for job {action.job_id}")
            
            # Update action status
            action.status = FollowUpStatus.SENT
            action.sent_at = datetime.now()
            
            # Store updated action
            await self._update_action(action)
            
            return True
            
        except Exception as e:
            logger.error(f"Error executing follow-up action: {e}")
            return False
    
    async def _store_strategy(self, strategy: FollowUpStrategy):
        """Store follow-up strategy in database"""
        try:
            # Store strategy and actions in database
            # This would involve database operations
            logger.info(f"Stored follow-up strategy for job {strategy.job_id}")
            
        except Exception as e:
            logger.error(f"Error storing follow-up strategy: {e}")
    
    async def _update_action(self, action: FollowUpAction):
        """Update follow-up action in database"""
        try:
            # Update action in database
            logger.info(f"Updated follow-up action {action.action_id}")
            
        except Exception as e:
            logger.error(f"Error updating follow-up action: {e}")

class FollowUpScheduler:
    """Handles scheduling and execution of follow-up actions"""
    
    def __init__(self):
        self.config = get_config()
        self.manager = FollowUpManager()
        
    async def process_daily_followups(self):
        """Process daily follow-up actions"""
        
        try:
            # Get pending follow-ups for today
            pending_actions = await self.manager.get_pending_followups(days_ahead=1)
            
            executed_count = 0
            for action in pending_actions:
                if await self.manager.execute_followup_action(action):
                    executed_count += 1
            
            logger.info(f"Executed {executed_count} follow-up actions")
            
        except Exception as e:
            logger.error(f"Error processing daily follow-ups: {e}")
    
    async def generate_followup_report(self) -> Dict[str, Any]:
        """Generate a follow-up performance report"""
        
        try:
            # This would query the database for follow-up statistics
            report = {
                'total_strategies': 0,
                'active_followups': 0,
                'response_rate': 0.0,
                'success_rate': 0.0,
                'top_performing_types': [],
                'recommendations': []
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating follow-up report: {e}")
            return {}

# Global instances
followup_manager = FollowUpManager()
followup_scheduler = FollowUpScheduler()

# Convenience functions
async def create_followup_strategy(job_data: Dict[str, Any],
                                 client_analysis: Any,
                                 application_data: Dict[str, Any]) -> FollowUpStrategy:
    """Create a follow-up strategy for a job application"""
    return await followup_manager.schedule_followup_strategy(job_data, client_analysis, application_data)

async def process_daily_followups():
    """Process daily follow-up actions"""
    await followup_scheduler.process_daily_followups()

async def get_followup_report() -> Dict[str, Any]:
    """Get follow-up performance report"""
    return await followup_scheduler.generate_followup_report()