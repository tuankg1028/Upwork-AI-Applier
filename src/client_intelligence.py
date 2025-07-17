import re
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import statistics
import hashlib

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config
from .utils import ainvoke_llm
from .database import get_database_manager

class ClientRiskLevel(Enum):
    """Client risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ClientType(Enum):
    """Client types based on behavior patterns"""
    ENTERPRISE = "enterprise"
    STARTUP = "startup"
    INDIVIDUAL = "individual"
    AGENCY = "agency"
    UNKNOWN = "unknown"

@dataclass
class ClientProfile:
    """Comprehensive client profile"""
    client_id: str
    name: Optional[str]
    location: str
    joined_date: str
    total_spent: str
    total_hires: int
    company_profile: Optional[str]
    
    # Calculated metrics
    avg_project_value: float
    hiring_frequency: float
    payment_reliability: float
    project_success_rate: float
    communication_quality: float
    scope_clarity: float
    
    # Risk assessment
    risk_level: ClientRiskLevel
    risk_factors: List[str]
    
    # Predictions
    success_probability: float
    estimated_response_time: float
    likely_project_value: float
    
    # Analysis timestamp
    analyzed_at: datetime

@dataclass
class ClientAnalysisResult:
    """Result of client analysis"""
    client_profile: ClientProfile
    match_score: float
    recommendations: List[str]
    red_flags: List[str]
    strengths: List[str]
    predicted_outcomes: Dict[str, float]

class ClientPatternAnalyzer:
    """Analyzes client patterns and behavior"""
    
    def __init__(self):
        self.config = get_config()
        self.db_manager = get_database_manager()
        
    def analyze_spending_patterns(self, total_spent: str, total_hires: int, joined_date: str) -> Dict[str, float]:
        """Analyze client spending patterns"""
        try:
            # Parse total spent
            spent_match = re.search(r'[\d,]+', total_spent.replace('$', '').replace(',', ''))
            total_amount = float(spent_match.group()) if spent_match else 0
            
            # Calculate average project value
            avg_project_value = total_amount / max(total_hires, 1)
            
            # Calculate hiring frequency (hires per month)
            joined_date_obj = datetime.strptime(joined_date, '%B %Y')
            months_active = max((datetime.now() - joined_date_obj).days / 30, 1)
            hiring_frequency = total_hires / months_active
            
            # Calculate spending velocity ($ per month)
            spending_velocity = total_amount / months_active
            
            return {
                'total_amount': total_amount,
                'avg_project_value': avg_project_value,
                'hiring_frequency': hiring_frequency,
                'spending_velocity': spending_velocity,
                'months_active': months_active
            }
            
        except Exception as e:
            logger.error(f"Error analyzing spending patterns: {e}")
            return {
                'total_amount': 0,
                'avg_project_value': 0,
                'hiring_frequency': 0,
                'spending_velocity': 0,
                'months_active': 1
            }
    
    def assess_payment_reliability(self, spending_data: Dict[str, float]) -> float:
        """Assess payment reliability based on spending patterns"""
        score = 50  # Base score
        
        # Higher spending indicates reliability
        if spending_data['total_amount'] > 10000:
            score += 30
        elif spending_data['total_amount'] > 5000:
            score += 20
        elif spending_data['total_amount'] > 1000:
            score += 10
        
        # Consistent hiring indicates reliability
        if spending_data['hiring_frequency'] > 2:
            score += 20
        elif spending_data['hiring_frequency'] > 1:
            score += 10
        
        # Long-term presence indicates stability
        if spending_data['months_active'] > 24:
            score += 20
        elif spending_data['months_active'] > 12:
            score += 10
        
        return min(100, max(0, score))
    
    def analyze_project_success_rate(self, total_hires: int, spending_data: Dict[str, float]) -> float:
        """Estimate project success rate"""
        # Base success rate assumptions
        if total_hires == 0:
            return 30  # Unknown, assume lower success rate
        
        # More hires generally indicate better success rate
        if total_hires > 20:
            base_rate = 85
        elif total_hires > 10:
            base_rate = 75
        elif total_hires > 5:
            base_rate = 65
        else:
            base_rate = 55
        
        # Adjust based on average project value
        if spending_data['avg_project_value'] > 5000:
            base_rate += 10  # Higher value projects tend to be more successful
        elif spending_data['avg_project_value'] < 500:
            base_rate -= 10  # Very low value projects may have issues
        
        return min(100, max(0, base_rate))
    
    def identify_client_type(self, company_profile: Optional[str], spending_data: Dict[str, float]) -> ClientType:
        """Identify client type based on available information"""
        if not company_profile:
            if spending_data['total_amount'] > 50000:
                return ClientType.ENTERPRISE
            elif spending_data['avg_project_value'] < 500:
                return ClientType.INDIVIDUAL
            else:
                return ClientType.UNKNOWN
        
        profile_lower = company_profile.lower()
        
        # Enterprise indicators
        enterprise_keywords = ['corporation', 'inc', 'llc', 'ltd', 'company', 'enterprise', 'solutions', 'systems']
        if any(keyword in profile_lower for keyword in enterprise_keywords):
            return ClientType.ENTERPRISE
        
        # Startup indicators
        startup_keywords = ['startup', 'tech', 'innovation', 'disrupt', 'scale', 'growth']
        if any(keyword in profile_lower for keyword in startup_keywords):
            return ClientType.STARTUP
        
        # Agency indicators
        agency_keywords = ['agency', 'marketing', 'design', 'creative', 'studio', 'media']
        if any(keyword in profile_lower for keyword in agency_keywords):
            return ClientType.AGENCY
        
        # Individual indicators
        individual_keywords = ['freelancer', 'consultant', 'personal', 'individual']
        if any(keyword in profile_lower for keyword in individual_keywords):
            return ClientType.INDIVIDUAL
        
        return ClientType.UNKNOWN
    
    def identify_red_flags(self, spending_data: Dict[str, float], company_profile: Optional[str]) -> List[str]:
        """Identify potential red flags"""
        red_flags = []
        
        # Low spending red flags
        if spending_data['total_amount'] < 100:
            red_flags.append("Very low total spending (< $100)")
        
        # Low hiring frequency
        if spending_data['hiring_frequency'] < 0.1:
            red_flags.append("Very low hiring frequency (< 0.1 per month)")
        
        # Unrealistic project values
        if spending_data['avg_project_value'] < 50:
            red_flags.append("Extremely low average project value (< $50)")
        
        # New account with high expectations
        if spending_data['months_active'] < 3 and spending_data['total_amount'] == 0:
            red_flags.append("New account with no spending history")
        
        # Profile analysis
        if company_profile:
            profile_lower = company_profile.lower()
            warning_keywords = ['urgent', 'asap', 'cheap', 'budget', 'fast', 'quick']
            if any(keyword in profile_lower for keyword in warning_keywords):
                red_flags.append("Profile contains urgency or budget-focused language")
        
        return red_flags
    
    def calculate_communication_quality(self, company_profile: Optional[str]) -> float:
        """Estimate communication quality based on profile"""
        if not company_profile:
            return 50  # Unknown
        
        score = 50
        
        # Length indicates effort
        if len(company_profile) > 500:
            score += 20
        elif len(company_profile) > 200:
            score += 10
        elif len(company_profile) < 50:
            score -= 20
        
        # Professional language
        professional_keywords = ['professional', 'experience', 'quality', 'skilled', 'expertise']
        if any(keyword in company_profile.lower() for keyword in professional_keywords):
            score += 15
        
        # Clear communication
        if '.' in company_profile and len(company_profile.split('.')) > 2:
            score += 10  # Multiple sentences indicate structure
        
        return min(100, max(0, score))

class ClientSuccessPredictor:
    """Predicts success probability for client interactions"""
    
    def __init__(self):
        self.config = get_config()
        self.pattern_analyzer = ClientPatternAnalyzer()
        
    @with_retry(operation_name="analyze_client")
    async def analyze_client(self, client_data: Dict[str, Any], job_context: Dict[str, Any]) -> ClientAnalysisResult:
        """Perform comprehensive client analysis"""
        with TimedOperation("client_analysis"):
            # Extract client information
            client_id = self._generate_client_id(client_data)
            
            # Analyze spending patterns
            spending_data = self.pattern_analyzer.analyze_spending_patterns(
                client_data.get('client_total_spent', '$0'),
                client_data.get('client_total_hires', 0),
                client_data.get('client_joined_date', 'January 2024')
            )
            
            # Calculate various metrics
            payment_reliability = self.pattern_analyzer.assess_payment_reliability(spending_data)
            project_success_rate = self.pattern_analyzer.analyze_project_success_rate(
                client_data.get('client_total_hires', 0),
                spending_data
            )
            
            communication_quality = self.pattern_analyzer.calculate_communication_quality(
                client_data.get('client_company_profile')
            )
            
            client_type = self.pattern_analyzer.identify_client_type(
                client_data.get('client_company_profile'),
                spending_data
            )
            
            red_flags = self.pattern_analyzer.identify_red_flags(
                spending_data,
                client_data.get('client_company_profile')
            )
            
            # Calculate risk level
            risk_level = self._calculate_risk_level(payment_reliability, project_success_rate, red_flags)
            
            # Predict success probability
            success_probability = await self._predict_success_probability(
                client_data,
                job_context,
                spending_data,
                payment_reliability,
                project_success_rate,
                communication_quality
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                client_type,
                spending_data,
                payment_reliability,
                red_flags,
                success_probability
            )
            
            # Identify strengths
            strengths = self._identify_strengths(
                spending_data,
                payment_reliability,
                project_success_rate,
                communication_quality
            )
            
            # Create client profile
            client_profile = ClientProfile(
                client_id=client_id,
                name=client_data.get('client_name'),
                location=client_data.get('client_location', 'Unknown'),
                joined_date=client_data.get('client_joined_date', 'Unknown'),
                total_spent=client_data.get('client_total_spent', '$0'),
                total_hires=client_data.get('client_total_hires', 0),
                company_profile=client_data.get('client_company_profile'),
                avg_project_value=spending_data['avg_project_value'],
                hiring_frequency=spending_data['hiring_frequency'],
                payment_reliability=payment_reliability,
                project_success_rate=project_success_rate,
                communication_quality=communication_quality,
                scope_clarity=self._estimate_scope_clarity(client_data),
                risk_level=risk_level,
                risk_factors=red_flags,
                success_probability=success_probability,
                estimated_response_time=self._estimate_response_time(client_type, spending_data),
                likely_project_value=self._estimate_project_value(spending_data, job_context),
                analyzed_at=datetime.now()
            )
            
            # Calculate match score
            match_score = self._calculate_match_score(client_profile, job_context)
            
            # Predict outcomes
            predicted_outcomes = {
                'response_probability': success_probability * 0.8,  # Slightly lower than success
                'interview_probability': success_probability * 0.6,
                'hire_probability': success_probability * 0.4,
                'project_completion_probability': project_success_rate / 100,
                'payment_probability': payment_reliability / 100
            }
            
            logger.info(f"Client analysis completed for {client_id}: success={success_probability:.1f}%, risk={risk_level.value}")
            
            return ClientAnalysisResult(
                client_profile=client_profile,
                match_score=match_score,
                recommendations=recommendations,
                red_flags=red_flags,
                strengths=strengths,
                predicted_outcomes=predicted_outcomes
            )
    
    def _generate_client_id(self, client_data: Dict[str, Any]) -> str:
        """Generate unique client ID"""
        # Use combination of location, joined date, and spending to create unique ID
        id_string = f"{client_data.get('client_location', '')}{client_data.get('client_joined_date', '')}{client_data.get('client_total_spent', '')}"
        return hashlib.md5(id_string.encode()).hexdigest()[:12]
    
    def _calculate_risk_level(self, payment_reliability: float, project_success_rate: float, red_flags: List[str]) -> ClientRiskLevel:
        """Calculate overall risk level"""
        if len(red_flags) >= 3:
            return ClientRiskLevel.CRITICAL
        elif len(red_flags) >= 2 or payment_reliability < 30:
            return ClientRiskLevel.HIGH
        elif len(red_flags) >= 1 or payment_reliability < 50 or project_success_rate < 50:
            return ClientRiskLevel.MEDIUM
        else:
            return ClientRiskLevel.LOW
    
    async def _predict_success_probability(self, client_data: Dict[str, Any], job_context: Dict[str, Any], 
                                         spending_data: Dict[str, float], payment_reliability: float,
                                         project_success_rate: float, communication_quality: float) -> float:
        """Predict success probability using AI analysis"""
        try:
            # Prepare context for AI analysis
            analysis_context = {
                'client_spending': spending_data,
                'payment_reliability': payment_reliability,
                'project_success_rate': project_success_rate,
                'communication_quality': communication_quality,
                'job_description': job_context.get('description', ''),
                'job_budget': job_context.get('payment_rate', ''),
                'client_profile': client_data.get('client_company_profile', '')
            }
            
            prediction_prompt = f"""
            Analyze this client and job combination to predict success probability:

            Client Analysis:
            - Total Spent: {client_data.get('client_total_spent', '$0')}
            - Total Hires: {client_data.get('client_total_hires', 0)}
            - Joined: {client_data.get('client_joined_date', 'Unknown')}
            - Location: {client_data.get('client_location', 'Unknown')}
            - Average Project Value: ${spending_data['avg_project_value']:.2f}
            - Hiring Frequency: {spending_data['hiring_frequency']:.2f} per month
            - Payment Reliability Score: {payment_reliability:.1f}%
            - Project Success Rate: {project_success_rate:.1f}%

            Job Context:
            - Description: {job_context.get('description', '')[:500]}
            - Budget: {job_context.get('payment_rate', 'Unknown')}
            - Experience Level: {job_context.get('experience_level', 'Unknown')}

            Based on this analysis, predict the success probability (0-100) for a freelancer applying to this job.
            Consider factors like client reliability, project fit, budget alignment, and communication quality.

            Return only a JSON object with:
            {{
                "success_probability": <number between 0-100>,
                "confidence": <number between 0-100>,
                "key_factors": ["factor1", "factor2", "factor3"],
                "reasoning": "Brief explanation of the prediction"
            }}
            """
            
            response = await ainvoke_llm(
                system_prompt="You are an expert freelance market analyst. Analyze client data and predict success probability for job applications.",
                user_message=prediction_prompt,
                model=self.config.llm.default_model
            )
            
            # Parse AI response
            try:
                prediction_data = json.loads(response)
                return float(prediction_data.get('success_probability', 50))
            except json.JSONDecodeError:
                logger.warning("Could not parse AI prediction response")
                return self._fallback_success_calculation(payment_reliability, project_success_rate, communication_quality)
                
        except Exception as e:
            logger.error(f"Error in AI success prediction: {e}")
            return self._fallback_success_calculation(payment_reliability, project_success_rate, communication_quality)
    
    def _fallback_success_calculation(self, payment_reliability: float, project_success_rate: float, communication_quality: float) -> float:
        """Fallback success calculation when AI prediction fails"""
        return statistics.mean([payment_reliability, project_success_rate, communication_quality])
    
    def _estimate_scope_clarity(self, client_data: Dict[str, Any]) -> float:
        """Estimate how clear the client is about project scope"""
        company_profile = client_data.get('client_company_profile', '')
        if not company_profile:
            return 50
        
        # Basic heuristics for scope clarity
        score = 50
        
        # Detailed profiles suggest better scope clarity
        if len(company_profile) > 300:
            score += 20
        elif len(company_profile) > 150:
            score += 10
        
        # Specific keywords indicate clarity
        clarity_keywords = ['specific', 'detailed', 'requirements', 'deliverables', 'timeline', 'budget']
        if any(keyword in company_profile.lower() for keyword in clarity_keywords):
            score += 15
        
        return min(100, max(0, score))
    
    def _estimate_response_time(self, client_type: ClientType, spending_data: Dict[str, float]) -> float:
        """Estimate how quickly client will respond (in hours)"""
        base_time = 48  # Default 48 hours
        
        # Adjust based on client type
        if client_type == ClientType.ENTERPRISE:
            base_time = 72  # Enterprises are slower
        elif client_type == ClientType.STARTUP:
            base_time = 24  # Startups are faster
        elif client_type == ClientType.INDIVIDUAL:
            base_time = 36  # Individuals are moderate
        
        # Adjust based on hiring frequency
        if spending_data['hiring_frequency'] > 2:
            base_time *= 0.8  # Active hirers respond faster
        elif spending_data['hiring_frequency'] < 0.5:
            base_time *= 1.5  # Inactive hirers respond slower
        
        return base_time
    
    def _estimate_project_value(self, spending_data: Dict[str, float], job_context: Dict[str, Any]) -> float:
        """Estimate likely project value"""
        # Start with historical average
        estimated_value = spending_data['avg_project_value']
        
        # Adjust based on job context
        payment_rate = job_context.get('payment_rate', '')
        if payment_rate:
            # Try to extract budget information
            budget_match = re.search(r'\$?(\d+)', payment_rate)
            if budget_match:
                budget_value = float(budget_match.group(1))
                # Use average of historical and posted budget
                estimated_value = (estimated_value + budget_value) / 2
        
        return max(estimated_value, 50)  # Minimum $50
    
    def _calculate_match_score(self, client_profile: ClientProfile, job_context: Dict[str, Any]) -> float:
        """Calculate how well this client matches our preferences"""
        score = 0
        
        # Payment reliability (30% weight)
        score += client_profile.payment_reliability * 0.3
        
        # Project success rate (25% weight)
        score += client_profile.project_success_rate * 0.25
        
        # Communication quality (20% weight)
        score += client_profile.communication_quality * 0.2
        
        # Project value (15% weight)
        value_score = min(100, (client_profile.avg_project_value / 1000) * 20)  # Score based on $1000 = 20 points
        score += value_score * 0.15
        
        # Risk level (10% weight)
        risk_score = {
            ClientRiskLevel.LOW: 100,
            ClientRiskLevel.MEDIUM: 60,
            ClientRiskLevel.HIGH: 30,
            ClientRiskLevel.CRITICAL: 0
        }
        score += risk_score[client_profile.risk_level] * 0.1
        
        return min(100, max(0, score))
    
    def _generate_recommendations(self, client_type: ClientType, spending_data: Dict[str, float],
                                payment_reliability: float, red_flags: List[str], success_probability: float) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # High-level strategy
        if success_probability > 80:
            recommendations.append("High-probability client - apply with premium positioning")
        elif success_probability > 60:
            recommendations.append("Good client potential - apply with standard approach")
        elif success_probability > 40:
            recommendations.append("Moderate risk - consider cautious approach or skip")
        else:
            recommendations.append("High risk client - consider avoiding")
        
        # Risk-based recommendations
        if len(red_flags) > 0:
            recommendations.append("Review red flags carefully before applying")
        
        if payment_reliability < 50:
            recommendations.append("Request milestone payments to mitigate payment risk")
        
        # Client type specific
        if client_type == ClientType.ENTERPRISE:
            recommendations.append("Emphasize corporate experience and formal processes")
        elif client_type == ClientType.STARTUP:
            recommendations.append("Highlight agility and growth-oriented experience")
        elif client_type == ClientType.INDIVIDUAL:
            recommendations.append("Focus on personal attention and direct communication")
        
        # Budget recommendations
        if spending_data['avg_project_value'] > 5000:
            recommendations.append("Position for premium pricing - client has budget for quality")
        elif spending_data['avg_project_value'] < 500:
            recommendations.append("Consider volume-based pricing or package deals")
        
        return recommendations
    
    def _identify_strengths(self, spending_data: Dict[str, float], payment_reliability: float,
                          project_success_rate: float, communication_quality: float) -> List[str]:
        """Identify client strengths"""
        strengths = []
        
        if payment_reliability > 80:
            strengths.append("Excellent payment reliability")
        elif payment_reliability > 60:
            strengths.append("Good payment history")
        
        if project_success_rate > 80:
            strengths.append("High project success rate")
        elif project_success_rate > 60:
            strengths.append("Decent project completion record")
        
        if communication_quality > 80:
            strengths.append("Clear communication style")
        elif communication_quality > 60:
            strengths.append("Good communication quality")
        
        if spending_data['avg_project_value'] > 2000:
            strengths.append("Invests in quality projects")
        
        if spending_data['hiring_frequency'] > 1:
            strengths.append("Active and consistent hiring")
        
        if spending_data['months_active'] > 12:
            strengths.append("Long-term platform presence")
        
        return strengths

# Global client success predictor instance
client_success_predictor = ClientSuccessPredictor()

# Convenience function
async def analyze_client_success(client_data: Dict[str, Any], job_context: Dict[str, Any]) -> ClientAnalysisResult:
    """Analyze client and predict success probability"""
    return await client_success_predictor.analyze_client(client_data, job_context)