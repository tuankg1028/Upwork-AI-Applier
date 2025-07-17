import json
import re
import asyncio
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config
from .utils import ainvoke_llm
from .client_intelligence import analyze_client_success, ClientRiskLevel

class ScoreConfidence(Enum):
    """Confidence levels for job scoring"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class JobCategory(Enum):
    """Job categories for specialized scoring"""
    DEVELOPMENT = "development"
    DESIGN = "design"
    WRITING = "writing"
    MARKETING = "marketing"
    DATA_SCIENCE = "data_science"
    AI_ML = "ai_ml"
    CONSULTING = "consulting"
    OTHER = "other"

@dataclass
class ScoringFactors:
    """Individual scoring factors with weights and scores"""
    skills_match: float = 0.0
    experience_level: float = 0.0
    budget_alignment: float = 0.0
    client_quality: float = 0.0
    job_description_quality: float = 0.0
    competition_level: float = 0.0
    timeline_feasibility: float = 0.0
    project_scope_clarity: float = 0.0
    long_term_potential: float = 0.0
    market_demand: float = 0.0

@dataclass
class ScoringResult:
    """Comprehensive scoring result"""
    job_id: str
    overall_score: float
    confidence: ScoreConfidence
    confidence_score: float
    factors: ScoringFactors
    factor_weights: Dict[str, float]
    category: JobCategory
    
    # Analysis details
    strengths: List[str]
    weaknesses: List[str]
    opportunities: List[str]
    threats: List[str]
    
    # Recommendations
    application_strategy: str
    recommended_rate: Optional[str]
    timeline_assessment: str
    risk_assessment: str
    
    # Metadata
    scored_at: datetime
    scoring_model: str
    explanation: str

class SkillMatcher:
    """Matches job requirements with freelancer skills"""
    
    def __init__(self, profile: str):
        self.profile = profile.lower()
        self.skills = self._extract_skills_from_profile()
        
    def _extract_skills_from_profile(self) -> List[str]:
        """Extract skills from freelancer profile"""
        # Common skill patterns
        skill_patterns = [
            r'\b(python|javascript|java|c\+\+|php|ruby|go|rust|kotlin|swift)\b',
            r'\b(react|angular|vue|nodejs|django|flask|spring|laravel)\b',
            r'\b(html|css|scss|sass|bootstrap|tailwind)\b',
            r'\b(mysql|postgresql|mongodb|redis|elasticsearch)\b',
            r'\b(aws|azure|gcp|docker|kubernetes|terraform)\b',
            r'\b(machine learning|deep learning|ai|nlp|computer vision)\b',
            r'\b(tensorflow|pytorch|scikit-learn|pandas|numpy)\b',
            r'\b(git|github|gitlab|jenkins|ci/cd|devops)\b',
            r'\b(wordpress|shopify|woocommerce|drupal|joomla)\b',
            r'\b(photoshop|illustrator|figma|sketch|adobe creative suite)\b',
            r'\b(seo|sem|google ads|facebook ads|content marketing)\b',
            r'\b(copywriting|technical writing|content writing|blogging)\b'
        ]
        
        skills = []
        for pattern in skill_patterns:
            matches = re.findall(pattern, self.profile, re.IGNORECASE)
            skills.extend(matches)
        
        return list(set(skills))  # Remove duplicates
    
    def calculate_skills_match(self, job_description: str, job_requirements: str) -> Tuple[float, List[str], List[str]]:
        """Calculate skills match score"""
        job_text = f"{job_description} {job_requirements}".lower()
        
        # Extract required skills from job
        required_skills = []
        for skill in self.skills:
            if skill in job_text:
                required_skills.append(skill)
        
        # Extract additional skills mentioned in job
        job_skills = []
        skill_keywords = ['experience', 'knowledge', 'proficient', 'skilled', 'expert', 'familiar']
        
        for keyword in skill_keywords:
            pattern = rf'{keyword}\s+(?:in|with|of)\s+([a-zA-Z0-9\s,]+)'
            matches = re.findall(pattern, job_text, re.IGNORECASE)
            for match in matches:
                skills_mentioned = [s.strip() for s in match.split(',')]
                job_skills.extend(skills_mentioned)
        
        # Calculate match percentage
        if not job_skills:
            return 50.0, required_skills, []  # No specific skills mentioned
        
        matched_skills = [skill for skill in job_skills if any(my_skill in skill.lower() for my_skill in self.skills)]
        
        if not job_skills:
            score = 50.0
        else:
            score = (len(matched_skills) / len(job_skills)) * 100
        
        missing_skills = [skill for skill in job_skills if skill not in matched_skills]
        
        return min(100, score), required_skills, missing_skills

class BudgetAnalyzer:
    """Analyzes job budget and alignment"""
    
    def __init__(self, target_rate: float = 50.0):
        self.target_rate = target_rate
        
    def analyze_budget(self, payment_rate: str, job_description: str) -> Tuple[float, str, str]:
        """Analyze budget alignment"""
        if not payment_rate:
            return 50.0, "unknown", "No budget information provided"
        
        # Extract budget information
        budget_info = self._extract_budget_info(payment_rate, job_description)
        
        if not budget_info:
            return 40.0, "unclear", "Budget information is unclear"
        
        # Calculate alignment score
        alignment_score = self._calculate_budget_alignment(budget_info)
        
        # Determine budget type
        budget_type = self._determine_budget_type(budget_info)
        
        # Generate analysis
        analysis = self._generate_budget_analysis(budget_info, alignment_score)
        
        return alignment_score, budget_type, analysis
    
    def _extract_budget_info(self, payment_rate: str, job_description: str) -> Optional[Dict[str, Any]]:
        """Extract budget information from text"""
        combined_text = f"{payment_rate} {job_description}"
        
        # Hourly rate patterns
        hourly_patterns = [
            r'\$?(\d+(?:\.\d{2})?)\s*(?:per|/)\s*hour',
            r'\$?(\d+(?:\.\d{2})?)\s*(?:hr|h)',
            r'hourly.*?\$?(\d+(?:\.\d{2})?)',
            r'\$?(\d+(?:\.\d{2})?)\s*hourly'
        ]
        
        # Fixed price patterns
        fixed_patterns = [
            r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:total|fixed|project)',
            r'budget.*?\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*for\s+(?:the|this)\s+project'
        ]
        
        # Range patterns
        range_patterns = [
            r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:to|-)\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'between\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:and|to)\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        # Try to find hourly rate
        for pattern in hourly_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                rate = float(match.group(1))
                return {
                    'type': 'hourly',
                    'rate': rate,
                    'min_rate': rate,
                    'max_rate': rate
                }
        
        # Try to find fixed price
        for pattern in fixed_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                price = float(match.group(1).replace(',', ''))
                return {
                    'type': 'fixed',
                    'rate': price,
                    'min_rate': price,
                    'max_rate': price
                }
        
        # Try to find range
        for pattern in range_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                min_rate = float(match.group(1).replace(',', ''))
                max_rate = float(match.group(2).replace(',', ''))
                return {
                    'type': 'range',
                    'rate': (min_rate + max_rate) / 2,
                    'min_rate': min_rate,
                    'max_rate': max_rate
                }
        
        return None
    
    def _calculate_budget_alignment(self, budget_info: Dict[str, Any]) -> float:
        """Calculate how well budget aligns with target rate"""
        if budget_info['type'] == 'hourly':
            if budget_info['rate'] >= self.target_rate:
                return 100.0
            else:
                return (budget_info['rate'] / self.target_rate) * 100
        
        elif budget_info['type'] == 'fixed':
            # Estimate hourly rate based on project scope
            estimated_hours = self._estimate_project_hours(budget_info['rate'])
            estimated_hourly = budget_info['rate'] / estimated_hours
            
            if estimated_hourly >= self.target_rate:
                return 100.0
            else:
                return (estimated_hourly / self.target_rate) * 100
        
        elif budget_info['type'] == 'range':
            # Use average of range
            avg_rate = (budget_info['min_rate'] + budget_info['max_rate']) / 2
            if avg_rate >= self.target_rate:
                return 100.0
            else:
                return (avg_rate / self.target_rate) * 100
        
        return 50.0  # Default score
    
    def _estimate_project_hours(self, fixed_price: float) -> float:
        """Estimate project hours based on fixed price"""
        # Basic heuristic: assume projects take 20-100 hours based on price
        if fixed_price < 500:
            return 20
        elif fixed_price < 2000:
            return 40
        elif fixed_price < 5000:
            return 60
        else:
            return 80
    
    def _determine_budget_type(self, budget_info: Dict[str, Any]) -> str:
        """Determine budget type category"""
        if budget_info['type'] == 'hourly':
            if budget_info['rate'] > 100:
                return "premium"
            elif budget_info['rate'] > 50:
                return "competitive"
            else:
                return "budget"
        
        elif budget_info['type'] == 'fixed':
            if budget_info['rate'] > 10000:
                return "large_project"
            elif budget_info['rate'] > 2000:
                return "medium_project"
            else:
                return "small_project"
        
        return "variable"
    
    def _generate_budget_analysis(self, budget_info: Dict[str, Any], alignment_score: float) -> str:
        """Generate budget analysis text"""
        if alignment_score >= 90:
            return f"Excellent budget alignment - ${budget_info['rate']:.2f} meets target rate"
        elif alignment_score >= 70:
            return f"Good budget alignment - ${budget_info['rate']:.2f} is competitive"
        elif alignment_score >= 50:
            return f"Moderate budget - ${budget_info['rate']:.2f} is below target but acceptable"
        else:
            return f"Low budget - ${budget_info['rate']:.2f} is significantly below target rate"

class EnhancedJobScorer:
    """Enhanced job scoring with weighted factors and confidence intervals"""
    
    def __init__(self, profile: str):
        self.profile = profile
        self.config = get_config()
        self.skill_matcher = SkillMatcher(profile)
        self.budget_analyzer = BudgetAnalyzer()
        
    @with_retry(operation_name="score_job_enhanced")
    async def score_job(self, job_data: Dict[str, Any]) -> ScoringResult:
        """Score job with enhanced weighted factors"""
        with TimedOperation("enhanced_job_scoring"):
            job_id = job_data.get('job_id', 'unknown')
            
            # Extract job information
            job_description = job_data.get('description', '')
            job_requirements = job_data.get('proposal_requirements', '')
            payment_rate = job_data.get('payment_rate', '')
            experience_level = job_data.get('experience_level', '')
            job_type = job_data.get('job_type', '')
            
            # Determine job category
            category = self._categorize_job(job_description, job_requirements)
            
            # Get category-specific weights
            factor_weights = self._get_category_weights(category)
            
            # Calculate individual factors
            factors = await self._calculate_all_factors(job_data)
            
            # Calculate weighted overall score
            overall_score = self._calculate_weighted_score(factors, factor_weights)
            
            # Calculate confidence level
            confidence, confidence_score = self._calculate_confidence(job_data, factors)
            
            # Perform SWOT analysis
            strengths, weaknesses, opportunities, threats = self._perform_swot_analysis(job_data, factors)
            
            # Generate recommendations
            application_strategy = self._generate_application_strategy(overall_score, factors, category)
            recommended_rate = self._recommend_rate(job_data, factors)
            timeline_assessment = self._assess_timeline(job_data, factors)
            risk_assessment = self._assess_risk(job_data, factors)
            
            # Generate explanation
            explanation = self._generate_explanation(overall_score, factors, category)
            
            result = ScoringResult(
                job_id=job_id,
                overall_score=overall_score,
                confidence=confidence,
                confidence_score=confidence_score,
                factors=factors,
                factor_weights=factor_weights,
                category=category,
                strengths=strengths,
                weaknesses=weaknesses,
                opportunities=opportunities,
                threats=threats,
                application_strategy=application_strategy,
                recommended_rate=recommended_rate,
                timeline_assessment=timeline_assessment,
                risk_assessment=risk_assessment,
                scored_at=datetime.now(),
                scoring_model="enhanced_v1.0",
                explanation=explanation
            )
            
            logger.info(f"Enhanced scoring completed for job {job_id}: {overall_score:.1f} ({confidence.value} confidence)")
            return result
    
    def _categorize_job(self, job_description: str, job_requirements: str) -> JobCategory:
        """Categorize job based on description and requirements"""
        combined_text = f"{job_description} {job_requirements}".lower()
        
        # Define category keywords
        category_keywords = {
            JobCategory.DEVELOPMENT: ['development', 'programming', 'coding', 'software', 'app', 'web', 'api', 'database'],
            JobCategory.DESIGN: ['design', 'ui', 'ux', 'graphic', 'visual', 'logo', 'branding', 'photoshop', 'illustrator'],
            JobCategory.WRITING: ['writing', 'content', 'copywriting', 'blog', 'article', 'documentation', 'technical writing'],
            JobCategory.MARKETING: ['marketing', 'seo', 'sem', 'social media', 'advertising', 'promotion', 'campaign'],
            JobCategory.DATA_SCIENCE: ['data science', 'analytics', 'data analysis', 'statistics', 'visualization', 'reporting'],
            JobCategory.AI_ML: ['ai', 'machine learning', 'artificial intelligence', 'deep learning', 'nlp', 'computer vision'],
            JobCategory.CONSULTING: ['consulting', 'strategy', 'business', 'advisory', 'planning', 'management']
        }
        
        # Score each category
        category_scores = {}
        for category, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in combined_text)
            category_scores[category] = score
        
        # Return category with highest score
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return JobCategory.OTHER
    
    def _get_category_weights(self, category: JobCategory) -> Dict[str, float]:
        """Get category-specific factor weights"""
        base_weights = self.config.scoring.weights
        
        # Adjust weights based on category
        if category == JobCategory.DEVELOPMENT:
            return {
                'skills_match': 0.35,
                'experience_level': 0.20,
                'budget_alignment': 0.20,
                'client_quality': 0.10,
                'job_description_quality': 0.05,
                'competition_level': 0.05,
                'timeline_feasibility': 0.05
            }
        elif category == JobCategory.DESIGN:
            return {
                'skills_match': 0.30,
                'client_quality': 0.25,
                'budget_alignment': 0.20,
                'job_description_quality': 0.10,
                'experience_level': 0.10,
                'timeline_feasibility': 0.05
            }
        elif category == JobCategory.WRITING:
            return {
                'skills_match': 0.25,
                'client_quality': 0.25,
                'budget_alignment': 0.25,
                'job_description_quality': 0.15,
                'timeline_feasibility': 0.10
            }
        else:
            # Use configured weights for other categories
            return base_weights
    
    async def _calculate_all_factors(self, job_data: Dict[str, Any]) -> ScoringFactors:
        """Calculate all scoring factors"""
        factors = ScoringFactors()
        
        # Skills match
        skills_score, _, _ = self.skill_matcher.calculate_skills_match(
            job_data.get('description', ''),
            job_data.get('proposal_requirements', '')
        )
        factors.skills_match = skills_score
        
        # Experience level alignment
        factors.experience_level = self._calculate_experience_alignment(job_data.get('experience_level', ''))
        
        # Budget alignment
        budget_score, _, _ = self.budget_analyzer.analyze_budget(
            job_data.get('payment_rate', ''),
            job_data.get('description', '')
        )
        factors.budget_alignment = budget_score
        
        # Client quality (using client intelligence)
        try:
            client_analysis = await analyze_client_success(job_data, {'description': job_data.get('description', '')})
            factors.client_quality = client_analysis.client_profile.success_probability
        except Exception as e:
            logger.warning(f"Client analysis failed: {e}")
            factors.client_quality = 50.0
        
        # Job description quality
        factors.job_description_quality = self._assess_job_description_quality(job_data.get('description', ''))
        
        # Competition level (estimated)
        factors.competition_level = self._estimate_competition_level(job_data)
        
        # Timeline feasibility
        factors.timeline_feasibility = self._assess_timeline_feasibility(job_data)
        
        # Project scope clarity
        factors.project_scope_clarity = self._assess_scope_clarity(job_data)
        
        # Long-term potential
        factors.long_term_potential = self._assess_long_term_potential(job_data)
        
        # Market demand
        factors.market_demand = self._assess_market_demand(job_data)
        
        return factors
    
    def _calculate_experience_alignment(self, experience_level: str) -> float:
        """Calculate experience level alignment"""
        if not experience_level:
            return 50.0
        
        level_lower = experience_level.lower()
        
        # Assume intermediate level freelancer
        if 'entry' in level_lower or 'beginner' in level_lower:
            return 90.0  # Good for beginners
        elif 'intermediate' in level_lower:
            return 100.0  # Perfect match
        elif 'expert' in level_lower or 'advanced' in level_lower:
            return 70.0  # Can compete but may be overqualified
        
        return 60.0  # Unknown level
    
    def _assess_job_description_quality(self, description: str) -> float:
        """Assess quality of job description"""
        if not description:
            return 0.0
        
        score = 50.0
        
        # Length indicates detail
        if len(description) > 1000:
            score += 20
        elif len(description) > 500:
            score += 10
        elif len(description) < 100:
            score -= 20
        
        # Structure indicators
        if description.count('\n') > 3:
            score += 10  # Multiple paragraphs
        
        if any(keyword in description.lower() for keyword in ['requirements', 'deliverables', 'timeline', 'budget']):
            score += 15
        
        # Warning signs
        if any(keyword in description.lower() for keyword in ['urgent', 'asap', 'cheap', 'quick']):
            score -= 10
        
        return min(100, max(0, score))
    
    def _estimate_competition_level(self, job_data: Dict[str, Any]) -> float:
        """Estimate competition level (inverse score - lower competition = higher score)"""
        # This is a simplified estimation
        # In real implementation, could use historical data or API
        
        budget = job_data.get('payment_rate', '')
        experience = job_data.get('experience_level', '')
        
        score = 50.0
        
        # Higher budget = lower competition
        if '$100' in budget or 'premium' in budget.lower():
            score += 30
        elif '$50' in budget or 'competitive' in budget.lower():
            score += 10
        elif '$20' in budget or 'budget' in budget.lower():
            score -= 20
        
        # Expert level = higher competition
        if 'expert' in experience.lower():
            score -= 20
        elif 'entry' in experience.lower():
            score += 20
        
        return min(100, max(0, score))
    
    def _assess_timeline_feasibility(self, job_data: Dict[str, Any]) -> float:
        """Assess timeline feasibility"""
        description = job_data.get('description', '').lower()
        
        # Look for timeline indicators
        if 'urgent' in description or 'asap' in description:
            return 30.0  # Unrealistic timeline
        elif 'flexible' in description or 'negotiable' in description:
            return 90.0  # Flexible timeline
        elif any(keyword in description for keyword in ['week', 'month', 'timeline']):
            return 70.0  # Reasonable timeline mentioned
        
        return 60.0  # No timeline information
    
    def _assess_scope_clarity(self, job_data: Dict[str, Any]) -> float:
        """Assess project scope clarity"""
        description = job_data.get('description', '')
        requirements = job_data.get('proposal_requirements', '')
        
        combined = f"{description} {requirements}"
        
        score = 50.0
        
        # Clear deliverables
        if any(keyword in combined.lower() for keyword in ['deliverables', 'requirements', 'specifications']):
            score += 20
        
        # Detailed description
        if len(combined) > 500:
            score += 15
        elif len(combined) < 100:
            score -= 20
        
        # Specific technologies mentioned
        if any(keyword in combined.lower() for keyword in ['python', 'react', 'javascript', 'design', 'wordpress']):
            score += 10
        
        return min(100, max(0, score))
    
    def _assess_long_term_potential(self, job_data: Dict[str, Any]) -> float:
        """Assess long-term relationship potential"""
        description = job_data.get('description', '').lower()
        
        score = 50.0
        
        # Indicators of long-term work
        if any(keyword in description for keyword in ['ongoing', 'long-term', 'partnership', 'relationship']):
            score += 30
        
        # One-time project indicators
        if any(keyword in description for keyword in ['one-time', 'single', 'quick']):
            score -= 20
        
        # Company size indicators
        if any(keyword in description for keyword in ['company', 'team', 'enterprise']):
            score += 15
        
        return min(100, max(0, score))
    
    def _assess_market_demand(self, job_data: Dict[str, Any]) -> float:
        """Assess market demand for this type of job"""
        description = job_data.get('description', '').lower()
        
        # High-demand skills
        high_demand_keywords = ['ai', 'machine learning', 'react', 'python', 'mobile app', 'e-commerce']
        if any(keyword in description for keyword in high_demand_keywords):
            return 80.0
        
        # Medium-demand skills
        medium_demand_keywords = ['web development', 'design', 'marketing', 'writing']
        if any(keyword in description for keyword in medium_demand_keywords):
            return 60.0
        
        return 50.0  # Average demand
    
    def _calculate_weighted_score(self, factors: ScoringFactors, weights: Dict[str, float]) -> float:
        """Calculate weighted overall score"""
        score = 0.0
        
        # Apply weights to factors
        for factor_name, weight in weights.items():
            factor_value = getattr(factors, factor_name, 0.0)
            score += factor_value * weight
        
        return min(100, max(0, score))
    
    def _calculate_confidence(self, job_data: Dict[str, Any], factors: ScoringFactors) -> Tuple[ScoreConfidence, float]:
        """Calculate confidence level in the score"""
        confidence_factors = []
        
        # Data completeness
        if job_data.get('description') and len(job_data.get('description', '')) > 200:
            confidence_factors.append(20)
        else:
            confidence_factors.append(5)
        
        # Budget clarity
        if job_data.get('payment_rate'):
            confidence_factors.append(15)
        else:
            confidence_factors.append(5)
        
        # Client information
        if job_data.get('client_total_spent') and job_data.get('client_total_hires'):
            confidence_factors.append(20)
        else:
            confidence_factors.append(5)
        
        # Skills match confidence
        if factors.skills_match > 70:
            confidence_factors.append(25)
        elif factors.skills_match > 40:
            confidence_factors.append(15)
        else:
            confidence_factors.append(5)
        
        # Job description quality
        if factors.job_description_quality > 70:
            confidence_factors.append(20)
        else:
            confidence_factors.append(10)
        
        confidence_score = sum(confidence_factors)
        
        if confidence_score >= 80:
            return ScoreConfidence.VERY_HIGH, confidence_score
        elif confidence_score >= 60:
            return ScoreConfidence.HIGH, confidence_score
        elif confidence_score >= 40:
            return ScoreConfidence.MEDIUM, confidence_score
        else:
            return ScoreConfidence.LOW, confidence_score
    
    def _perform_swot_analysis(self, job_data: Dict[str, Any], factors: ScoringFactors) -> Tuple[List[str], List[str], List[str], List[str]]:
        """Perform SWOT analysis"""
        strengths = []
        weaknesses = []
        opportunities = []
        threats = []
        
        # Strengths
        if factors.skills_match > 80:
            strengths.append("Excellent skills match")
        if factors.client_quality > 75:
            strengths.append("High-quality client")
        if factors.budget_alignment > 80:
            strengths.append("Budget aligns well with rates")
        
        # Weaknesses
        if factors.skills_match < 50:
            weaknesses.append("Limited skills match")
        if factors.budget_alignment < 40:
            weaknesses.append("Budget below target rate")
        if factors.experience_level < 60:
            weaknesses.append("Experience level mismatch")
        
        # Opportunities
        if factors.long_term_potential > 70:
            opportunities.append("Potential for long-term relationship")
        if factors.market_demand > 70:
            opportunities.append("High market demand for these skills")
        if factors.competition_level > 70:
            opportunities.append("Lower competition expected")
        
        # Threats
        if factors.competition_level < 30:
            threats.append("High competition expected")
        if factors.timeline_feasibility < 40:
            threats.append("Unrealistic timeline requirements")
        if factors.client_quality < 40:
            threats.append("Client reliability concerns")
        
        return strengths, weaknesses, opportunities, threats
    
    def _generate_application_strategy(self, overall_score: float, factors: ScoringFactors, category: JobCategory) -> str:
        """Generate application strategy"""
        if overall_score >= 80:
            return "High-priority application: Apply quickly with premium positioning"
        elif overall_score >= 60:
            return "Good opportunity: Apply with standard approach, emphasize relevant experience"
        elif overall_score >= 40:
            return "Moderate opportunity: Consider applying if pipeline is light, address potential concerns"
        else:
            return "Low-priority: Consider skipping unless strategic reasons apply"
    
    def _recommend_rate(self, job_data: Dict[str, Any], factors: ScoringFactors) -> Optional[str]:
        """Recommend rate strategy"""
        if factors.budget_alignment > 80 and factors.client_quality > 70:
            return "Premium rate - client can afford quality"
        elif factors.budget_alignment > 60:
            return "Standard rate - competitive positioning"
        elif factors.budget_alignment < 40:
            return "Consider value-based pricing or packages"
        else:
            return "Flexible rate strategy based on client discussion"
    
    def _assess_timeline(self, job_data: Dict[str, Any], factors: ScoringFactors) -> str:
        """Assess timeline feasibility"""
        if factors.timeline_feasibility > 80:
            return "Timeline appears realistic and achievable"
        elif factors.timeline_feasibility > 60:
            return "Timeline may be tight but manageable"
        elif factors.timeline_feasibility > 40:
            return "Timeline concerns - may need negotiation"
        else:
            return "Timeline appears unrealistic - proceed with caution"
    
    def _assess_risk(self, job_data: Dict[str, Any], factors: ScoringFactors) -> str:
        """Assess overall risk level"""
        risk_factors = []
        
        if factors.client_quality < 50:
            risk_factors.append("Client reliability")
        if factors.budget_alignment < 40:
            risk_factors.append("Budget mismatch")
        if factors.project_scope_clarity < 50:
            risk_factors.append("Unclear scope")
        if factors.timeline_feasibility < 40:
            risk_factors.append("Unrealistic timeline")
        
        if not risk_factors:
            return "Low risk - proceed with confidence"
        elif len(risk_factors) == 1:
            return f"Medium risk - monitor {risk_factors[0]}"
        else:
            return f"High risk - multiple concerns: {', '.join(risk_factors)}"
    
    def _generate_explanation(self, overall_score: float, factors: ScoringFactors, category: JobCategory) -> str:
        """Generate scoring explanation"""
        explanation = f"Score: {overall_score:.1f}/100 for {category.value} project. "
        
        # Highlight top factors
        factor_scores = {
            'Skills Match': factors.skills_match,
            'Client Quality': factors.client_quality,
            'Budget Alignment': factors.budget_alignment,
            'Experience Level': factors.experience_level,
            'Job Description Quality': factors.job_description_quality
        }
        
        # Sort by score
        sorted_factors = sorted(factor_scores.items(), key=lambda x: x[1], reverse=True)
        
        explanation += f"Top factors: {sorted_factors[0][0]} ({sorted_factors[0][1]:.1f}), "
        explanation += f"{sorted_factors[1][0]} ({sorted_factors[1][1]:.1f}). "
        
        # Add recommendation
        if overall_score >= 70:
            explanation += "Strong recommendation to apply."
        elif overall_score >= 50:
            explanation += "Moderate recommendation - consider based on pipeline."
        else:
            explanation += "Weak recommendation - multiple concerns identified."
        
        return explanation

# Global enhanced job scorer
def create_enhanced_scorer(profile: str) -> EnhancedJobScorer:
    """Create enhanced job scorer instance"""
    return EnhancedJobScorer(profile)

# Convenience function for batch scoring
async def score_jobs_enhanced(jobs: List[Dict[str, Any]], profile: str) -> List[ScoringResult]:
    """Score multiple jobs with enhanced scoring"""
    scorer = create_enhanced_scorer(profile)
    results = []
    
    for job in jobs:
        try:
            result = await scorer.score_job(job)
            results.append(result)
        except Exception as e:
            logger.error(f"Error scoring job {job.get('job_id', 'unknown')}: {e}")
            # Create default result for failed scoring
            results.append(ScoringResult(
                job_id=job.get('job_id', 'unknown'),
                overall_score=0.0,
                confidence=ScoreConfidence.LOW,
                confidence_score=0.0,
                factors=ScoringFactors(),
                factor_weights={},
                category=JobCategory.OTHER,
                strengths=[],
                weaknesses=["Scoring failed"],
                opportunities=[],
                threats=["Unable to analyze"],
                application_strategy="Skip - analysis failed",
                recommended_rate=None,
                timeline_assessment="Unknown",
                risk_assessment="High - analysis failed",
                scored_at=datetime.now(),
                scoring_model="enhanced_v1.0",
                explanation="Job scoring failed due to technical error"
            ))
    
    return results