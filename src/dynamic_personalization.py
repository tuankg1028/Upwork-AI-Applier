import re
import json
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
from urllib.parse import urlparse, urljoin
import time

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config
from .utils import ainvoke_llm
from .client_intelligence import ClientAnalysisResult

class PersonalizationLevel(Enum):
    """Levels of personalization depth"""
    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"
    PREMIUM = "premium"

class ResearchSource(Enum):
    """Sources of research information"""
    COMPANY_WEBSITE = "company_website"
    SOCIAL_MEDIA = "social_media"
    NEWS_ARTICLES = "news_articles"
    INDUSTRY_REPORTS = "industry_reports"
    CLIENT_PROFILE = "client_profile"
    JOB_DESCRIPTION = "job_description"

@dataclass
class CompanyResearch:
    """Company research data"""
    company_name: str
    website_url: Optional[str]
    industry: str
    company_size: str
    location: str
    
    # Business insights
    business_model: str
    target_market: str
    key_services: List[str]
    recent_news: List[str]
    challenges: List[str]
    opportunities: List[str]
    
    # Technology stack
    technologies_used: List[str]
    tech_stack_analysis: str
    
    # Competitive analysis
    competitors: List[str]
    market_position: str
    
    # Financial insights
    funding_info: Optional[str]
    revenue_estimate: Optional[str]
    growth_stage: str
    
    # Research metadata
    research_sources: List[ResearchSource]
    research_confidence: float
    last_updated: datetime

@dataclass
class IndustryInsights:
    """Industry-specific insights"""
    industry_name: str
    market_trends: List[str]
    growth_opportunities: List[str]
    common_challenges: List[str]
    key_technologies: List[str]
    regulatory_considerations: List[str]
    best_practices: List[str]
    success_metrics: List[str]
    
    # Market data
    market_size: Optional[str]
    growth_rate: Optional[str]
    key_players: List[str]
    
    # Technology adoption
    emerging_technologies: List[str]
    technology_adoption_rate: str
    
    # Generated insights
    insights_generated_at: datetime
    insights_confidence: float

@dataclass
class PersonalizationContext:
    """Context for proposal personalization"""
    company_research: Optional[CompanyResearch]
    industry_insights: Optional[IndustryInsights]
    client_analysis: Optional[ClientAnalysisResult]
    job_specific_insights: Dict[str, Any]
    market_context: Dict[str, Any]
    personalization_level: PersonalizationLevel
    
    # Personalization factors
    pain_points: List[str]
    value_propositions: List[str]
    relevant_experience: List[str]
    custom_talking_points: List[str]
    
    # Content customization
    tone_adjustments: Dict[str, str]
    industry_terminology: List[str]
    company_specific_keywords: List[str]
    
    # Strategic positioning
    competitive_advantages: List[str]
    positioning_strategy: str
    pricing_strategy: str

class CompanyResearcher:
    """Researches companies and extracts business insights"""
    
    def __init__(self):
        self.config = get_config()
        self.session = None
        self.research_cache = {}
        
    async def _get_session(self):
        """Get or create aiohttp session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    @with_retry(operation_name="research_company")
    async def research_company(self, company_name: str, website_url: Optional[str] = None,
                             location: str = "Unknown") -> CompanyResearch:
        """Conduct comprehensive company research"""
        with TimedOperation("company_research"):
            # Check cache first
            cache_key = hashlib.md5(f"{company_name}_{website_url}".encode()).hexdigest()
            if cache_key in self.research_cache:
                cached_result = self.research_cache[cache_key]
                if (datetime.now() - cached_result.last_updated).hours < 24:
                    logger.debug(f"Using cached research for {company_name}")
                    return cached_result
            
            research_sources = []
            
            # Initialize research data
            research_data = {
                'company_name': company_name,
                'website_url': website_url,
                'location': location,
                'industry': 'Unknown',
                'company_size': 'Unknown',
                'business_model': 'Unknown',
                'target_market': 'Unknown',
                'key_services': [],
                'recent_news': [],
                'challenges': [],
                'opportunities': [],
                'technologies_used': [],
                'tech_stack_analysis': '',
                'competitors': [],
                'market_position': 'Unknown',
                'funding_info': None,
                'revenue_estimate': None,
                'growth_stage': 'Unknown'
            }
            
            # Research from website
            if website_url:
                website_data = await self._research_from_website(website_url)
                research_data.update(website_data)
                research_sources.append(ResearchSource.COMPANY_WEBSITE)
            
            # Research from company name
            name_research = await self._research_from_company_name(company_name)
            research_data.update(name_research)
            research_sources.append(ResearchSource.CLIENT_PROFILE)
            
            # AI-powered analysis
            ai_insights = await self._generate_ai_insights(research_data)
            research_data.update(ai_insights)
            
            # Calculate confidence
            confidence = self._calculate_research_confidence(research_data, research_sources)
            
            # Create research object
            company_research = CompanyResearch(
                company_name=research_data['company_name'],
                website_url=research_data['website_url'],
                industry=research_data['industry'],
                company_size=research_data['company_size'],
                location=research_data['location'],
                business_model=research_data['business_model'],
                target_market=research_data['target_market'],
                key_services=research_data['key_services'],
                recent_news=research_data['recent_news'],
                challenges=research_data['challenges'],
                opportunities=research_data['opportunities'],
                technologies_used=research_data['technologies_used'],
                tech_stack_analysis=research_data['tech_stack_analysis'],
                competitors=research_data['competitors'],
                market_position=research_data['market_position'],
                funding_info=research_data['funding_info'],
                revenue_estimate=research_data['revenue_estimate'],
                growth_stage=research_data['growth_stage'],
                research_sources=research_sources,
                research_confidence=confidence,
                last_updated=datetime.now()
            )
            
            # Cache result
            self.research_cache[cache_key] = company_research
            
            logger.info(f"Completed research for {company_name} (confidence: {confidence:.1f}%)")
            return company_research
    
    async def _research_from_website(self, website_url: str) -> Dict[str, Any]:
        """Research company from their website"""
        try:
            session = await self._get_session()
            
            # Fetch website content
            async with session.get(website_url) as response:
                if response.status == 200:
                    content = await response.text()
                    return self._extract_website_insights(content, website_url)
                else:
                    logger.warning(f"Failed to fetch website {website_url}: {response.status}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error researching website {website_url}: {e}")
            return {}
    
    def _extract_website_insights(self, html_content: str, website_url: str) -> Dict[str, Any]:
        """Extract insights from website HTML"""
        insights = {}
        
        # Extract title and meta description
        title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
        if title_match:
            insights['page_title'] = title_match.group(1).strip()
        
        # Extract meta description
        meta_desc = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
        if meta_desc:
            insights['meta_description'] = meta_desc.group(1).strip()
        
        # Extract keywords
        keywords = re.search(r'<meta\s+name=["\']keywords["\']\s+content=["\']([^"\']*)["\']', html_content, re.IGNORECASE)
        if keywords:
            insights['keywords'] = [k.strip() for k in keywords.group(1).split(',')]
        
        # Extract technology stack indicators
        tech_indicators = {
            'react': r'react',
            'angular': r'angular',
            'vue': r'vue',
            'wordpress': r'wp-content|wordpress',
            'shopify': r'shopify',
            'django': r'django',
            'rails': r'rails',
            'node': r'node\.js|nodejs',
            'python': r'python',
            'php': r'php'
        }
        
        technologies = []
        for tech, pattern in tech_indicators.items():
            if re.search(pattern, html_content, re.IGNORECASE):
                technologies.append(tech)
        
        insights['technologies_used'] = technologies
        
        # Extract company size indicators
        team_indicators = ['team', 'employees', 'staff', 'people']
        for indicator in team_indicators:
            pattern = rf'{indicator}[^0-9]*(\d+)'
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                size = int(match.group(1))
                if size < 10:
                    insights['company_size'] = 'Small (< 10 employees)'
                elif size < 50:
                    insights['company_size'] = 'Medium (10-50 employees)'
                else:
                    insights['company_size'] = 'Large (50+ employees)'
                break
        
        # Extract industry indicators
        industry_keywords = {
            'technology': ['software', 'tech', 'development', 'digital', 'IT'],
            'healthcare': ['health', 'medical', 'healthcare', 'hospital', 'clinic'],
            'finance': ['finance', 'banking', 'fintech', 'investment', 'financial'],
            'ecommerce': ['ecommerce', 'online store', 'retail', 'shopping'],
            'education': ['education', 'learning', 'school', 'university', 'training'],
            'marketing': ['marketing', 'advertising', 'agency', 'branding', 'digital marketing']
        }
        
        content_lower = html_content.lower()
        for industry, keywords in industry_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                insights['industry'] = industry.title()
                break
        
        return insights
    
    async def _research_from_company_name(self, company_name: str) -> Dict[str, Any]:
        """Research company from name using AI analysis"""
        try:
            research_prompt = f"""
            Analyze this company name and provide business insights: "{company_name}"
            
            Based on the company name, provide educated estimates about:
            1. Industry/sector
            2. Likely business model
            3. Target market
            4. Company size estimate
            5. Common challenges in this industry
            6. Growth opportunities
            7. Typical technology stack
            8. Key competitors (if recognizable)
            
            Return a JSON object with your analysis:
            {{
                "industry": "estimated industry",
                "business_model": "B2B/B2C/marketplace/etc",
                "target_market": "who they likely serve",
                "company_size": "startup/small/medium/large",
                "challenges": ["challenge1", "challenge2"],
                "opportunities": ["opportunity1", "opportunity2"],
                "technologies_used": ["tech1", "tech2"],
                "competitors": ["competitor1", "competitor2"],
                "growth_stage": "seed/growth/mature/enterprise"
            }}
            """
            
            response = await ainvoke_llm(
                system_prompt="You are a business analyst expert. Analyze company names and provide insights about their likely business characteristics.",
                user_message=research_prompt,
                model=self.config.llm.default_model
            )
            
            # Parse AI response
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.warning("Could not parse AI company research response")
                return {}
                
        except Exception as e:
            logger.error(f"Error in AI company research: {e}")
            return {}
    
    async def _generate_ai_insights(self, research_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate additional AI insights from collected data"""
        try:
            insights_prompt = f"""
            Based on this company research data, provide additional strategic insights:
            
            Company: {research_data['company_name']}
            Industry: {research_data.get('industry', 'Unknown')}
            Technologies: {research_data.get('technologies_used', [])}
            Business Model: {research_data.get('business_model', 'Unknown')}
            
            Provide insights about:
            1. Likely pain points and challenges
            2. Technology modernization opportunities
            3. Market positioning strategy
            4. Competitive advantages they might need
            5. Key success metrics they likely track
            
            Return JSON:
            {{
                "pain_points": ["pain1", "pain2"],
                "tech_opportunities": ["opportunity1", "opportunity2"],
                "market_position": "position description",
                "competitive_advantages": ["advantage1", "advantage2"],
                "success_metrics": ["metric1", "metric2"]
            }}
            """
            
            response = await ainvoke_llm(
                system_prompt="You are a strategic business consultant. Analyze company data and provide actionable insights.",
                user_message=insights_prompt,
                model=self.config.llm.default_model
            )
            
            try:
                insights = json.loads(response)
                return {
                    'challenges': insights.get('pain_points', []),
                    'opportunities': insights.get('tech_opportunities', []),
                    'market_position': insights.get('market_position', 'Unknown'),
                    'competitive_advantages': insights.get('competitive_advantages', []),
                    'success_metrics': insights.get('success_metrics', [])
                }
            except json.JSONDecodeError:
                logger.warning("Could not parse AI insights response")
                return {}
                
        except Exception as e:
            logger.error(f"Error generating AI insights: {e}")
            return {}
    
    def _calculate_research_confidence(self, research_data: Dict[str, Any], sources: List[ResearchSource]) -> float:
        """Calculate confidence in research data"""
        confidence = 0.0
        
        # Base confidence from sources
        if ResearchSource.COMPANY_WEBSITE in sources:
            confidence += 40.0
        if ResearchSource.CLIENT_PROFILE in sources:
            confidence += 20.0
        
        # Data completeness bonus
        if research_data.get('industry') != 'Unknown':
            confidence += 15.0
        if research_data.get('technologies_used'):
            confidence += 10.0
        if research_data.get('challenges'):
            confidence += 10.0
        if research_data.get('opportunities'):
            confidence += 5.0
        
        return min(100.0, confidence)

class IndustryAnalyzer:
    """Analyzes industry trends and provides insights"""
    
    def __init__(self):
        self.config = get_config()
        self.industry_cache = {}
    
    @with_retry(operation_name="analyze_industry")
    async def analyze_industry(self, industry: str, company_context: Optional[Dict[str, Any]] = None) -> IndustryInsights:
        """Analyze industry trends and provide insights"""
        with TimedOperation("industry_analysis"):
            # Check cache
            cache_key = hashlib.md5(industry.encode()).hexdigest()
            if cache_key in self.industry_cache:
                cached_result = self.industry_cache[cache_key]
                if (datetime.now() - cached_result.insights_generated_at).hours < 48:
                    logger.debug(f"Using cached industry analysis for {industry}")
                    return cached_result
            
            # Generate industry insights using AI
            insights = await self._generate_industry_insights(industry, company_context)
            
            # Cache result
            self.industry_cache[cache_key] = insights
            
            logger.info(f"Completed industry analysis for {industry}")
            return insights
    
    async def _generate_industry_insights(self, industry: str, company_context: Optional[Dict[str, Any]] = None) -> IndustryInsights:
        """Generate comprehensive industry insights"""
        try:
            context_str = ""
            if company_context:
                context_str = f"Company context: {json.dumps(company_context, indent=2)}"
            
            industry_prompt = f"""
            Provide comprehensive analysis for the {industry} industry:
            
            {context_str}
            
            Analysis needed:
            1. Current market trends and directions
            2. Growth opportunities and emerging segments
            3. Common challenges and pain points
            4. Key technologies and tools being adopted
            5. Regulatory considerations and compliance requirements
            6. Industry best practices and standards
            7. Success metrics and KPIs
            8. Market size and growth projections
            9. Key market players and competitors
            10. Emerging technologies and innovation areas
            
            Return detailed JSON:
            {{
                "market_trends": ["trend1", "trend2", "trend3"],
                "growth_opportunities": ["opportunity1", "opportunity2"],
                "common_challenges": ["challenge1", "challenge2"],
                "key_technologies": ["tech1", "tech2", "tech3"],
                "regulatory_considerations": ["regulation1", "regulation2"],
                "best_practices": ["practice1", "practice2"],
                "success_metrics": ["metric1", "metric2"],
                "market_size": "size estimate",
                "growth_rate": "growth percentage",
                "key_players": ["player1", "player2", "player3"],
                "emerging_technologies": ["emerging1", "emerging2"],
                "technology_adoption_rate": "adoption description"
            }}
            """
            
            response = await ainvoke_llm(
                system_prompt="You are an industry research expert with deep knowledge of market trends, technologies, and business strategies across all industries.",
                user_message=industry_prompt,
                model=self.config.llm.default_model
            )
            
            # Parse response
            try:
                insights_data = json.loads(response)
                
                return IndustryInsights(
                    industry_name=industry,
                    market_trends=insights_data.get('market_trends', []),
                    growth_opportunities=insights_data.get('growth_opportunities', []),
                    common_challenges=insights_data.get('common_challenges', []),
                    key_technologies=insights_data.get('key_technologies', []),
                    regulatory_considerations=insights_data.get('regulatory_considerations', []),
                    best_practices=insights_data.get('best_practices', []),
                    success_metrics=insights_data.get('success_metrics', []),
                    market_size=insights_data.get('market_size'),
                    growth_rate=insights_data.get('growth_rate'),
                    key_players=insights_data.get('key_players', []),
                    emerging_technologies=insights_data.get('emerging_technologies', []),
                    technology_adoption_rate=insights_data.get('technology_adoption_rate', 'Unknown'),
                    insights_generated_at=datetime.now(),
                    insights_confidence=85.0  # AI-generated insights have good confidence
                )
                
            except json.JSONDecodeError:
                logger.warning("Could not parse industry insights response")
                return self._create_fallback_insights(industry)
                
        except Exception as e:
            logger.error(f"Error generating industry insights: {e}")
            return self._create_fallback_insights(industry)
    
    def _create_fallback_insights(self, industry: str) -> IndustryInsights:
        """Create fallback insights when AI analysis fails"""
        return IndustryInsights(
            industry_name=industry,
            market_trends=["Digital transformation", "Remote work adoption"],
            growth_opportunities=["Technology adoption", "Process optimization"],
            common_challenges=["Competition", "Technology modernization"],
            key_technologies=["Cloud computing", "AI/ML", "Mobile technologies"],
            regulatory_considerations=["Data privacy", "Security compliance"],
            best_practices=["Customer focus", "Innovation", "Quality delivery"],
            success_metrics=["Customer satisfaction", "Revenue growth", "Market share"],
            market_size="Analysis unavailable",
            growth_rate="Analysis unavailable",
            key_players=["Industry leaders", "Emerging players"],
            emerging_technologies=["AI/ML", "Automation", "IoT"],
            technology_adoption_rate="Moderate to high",
            insights_generated_at=datetime.now(),
            insights_confidence=30.0  # Lower confidence for fallback
        )

class DynamicPersonalizationEngine:
    """Main engine for dynamic proposal personalization"""
    
    def __init__(self):
        self.config = get_config()
        self.company_researcher = CompanyResearcher()
        self.industry_analyzer = IndustryAnalyzer()
    
    async def close(self):
        """Close connections"""
        await self.company_researcher.close()
    
    @with_retry(operation_name="personalize_proposal")
    async def personalize_proposal(self, job_data: Dict[str, Any], client_analysis: Optional[ClientAnalysisResult] = None,
                                 personalization_level: PersonalizationLevel = PersonalizationLevel.STANDARD) -> PersonalizationContext:
        """Create personalized proposal context"""
        with TimedOperation("proposal_personalization"):
            # Extract company information
            company_name = self._extract_company_name(job_data)
            website_url = self._extract_website_url(job_data)
            
            # Research company
            company_research = None
            if company_name and personalization_level in [PersonalizationLevel.ADVANCED, PersonalizationLevel.PREMIUM]:
                try:
                    company_research = await self.company_researcher.research_company(
                        company_name, 
                        website_url, 
                        job_data.get('client_location', 'Unknown')
                    )
                except Exception as e:
                    logger.error(f"Company research failed: {e}")
            
            # Analyze industry
            industry_insights = None
            if company_research and company_research.industry != 'Unknown':
                try:
                    industry_insights = await self.industry_analyzer.analyze_industry(
                        company_research.industry,
                        {'company_name': company_name, 'company_size': company_research.company_size}
                    )
                except Exception as e:
                    logger.error(f"Industry analysis failed: {e}")
            
            # Generate personalization context
            context = await self._generate_personalization_context(
                job_data, 
                company_research, 
                industry_insights, 
                client_analysis, 
                personalization_level
            )
            
            logger.info(f"Generated personalization context for {company_name or 'Unknown Company'}")
            return context
    
    def _extract_company_name(self, job_data: Dict[str, Any]) -> Optional[str]:
        """Extract company name from job data"""
        # Try various fields
        company_sources = [
            job_data.get('client_company_profile', ''),
            job_data.get('description', ''),
            job_data.get('client_location', '')
        ]
        
        for source in company_sources:
            if source:
                # Look for company name patterns
                company_patterns = [
                    r'(?:company|firm|corporation|inc|llc|ltd)[:\s]+([A-Za-z\s]+)',
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:inc|llc|ltd|corp|company)',
                    r'at\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                    r'for\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
                ]
                
                for pattern in company_patterns:
                    match = re.search(pattern, source, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
        
        return None
    
    def _extract_website_url(self, job_data: Dict[str, Any]) -> Optional[str]:
        """Extract website URL from job data"""
        text_sources = [
            job_data.get('client_company_profile', ''),
            job_data.get('description', '')
        ]
        
        url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
        
        for source in text_sources:
            if source:
                match = re.search(url_pattern, source)
                if match:
                    return match.group(0)
        
        return None
    
    async def _generate_personalization_context(self, job_data: Dict[str, Any], 
                                              company_research: Optional[CompanyResearch],
                                              industry_insights: Optional[IndustryInsights],
                                              client_analysis: Optional[ClientAnalysisResult],
                                              personalization_level: PersonalizationLevel) -> PersonalizationContext:
        """Generate comprehensive personalization context"""
        
        # Extract job-specific insights
        job_insights = self._extract_job_insights(job_data)
        
        # Generate pain points
        pain_points = self._identify_pain_points(job_data, company_research, industry_insights)
        
        # Generate value propositions
        value_propositions = self._generate_value_propositions(job_data, company_research, industry_insights)
        
        # Extract relevant experience
        relevant_experience = self._extract_relevant_experience(job_data, company_research, industry_insights)
        
        # Generate custom talking points
        talking_points = await self._generate_talking_points(job_data, company_research, industry_insights)
        
        # Determine tone adjustments
        tone_adjustments = self._determine_tone_adjustments(client_analysis, company_research)
        
        # Extract industry terminology
        industry_terminology = self._extract_industry_terminology(industry_insights)
        
        # Generate company-specific keywords
        company_keywords = self._generate_company_keywords(company_research)
        
        # Determine competitive advantages
        competitive_advantages = self._identify_competitive_advantages(job_data, company_research, industry_insights)
        
        # Generate positioning strategy
        positioning_strategy = self._generate_positioning_strategy(client_analysis, company_research, personalization_level)
        
        # Generate pricing strategy
        pricing_strategy = self._generate_pricing_strategy(client_analysis, company_research, job_data)
        
        return PersonalizationContext(
            company_research=company_research,
            industry_insights=industry_insights,
            client_analysis=client_analysis,
            job_specific_insights=job_insights,
            market_context={},
            personalization_level=personalization_level,
            pain_points=pain_points,
            value_propositions=value_propositions,
            relevant_experience=relevant_experience,
            custom_talking_points=talking_points,
            tone_adjustments=tone_adjustments,
            industry_terminology=industry_terminology,
            company_specific_keywords=company_keywords,
            competitive_advantages=competitive_advantages,
            positioning_strategy=positioning_strategy,
            pricing_strategy=pricing_strategy
        )
    
    def _extract_job_insights(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract insights from job description"""
        description = job_data.get('description', '')
        requirements = job_data.get('proposal_requirements', '')
        
        # Extract urgency indicators
        urgency_keywords = ['urgent', 'asap', 'immediately', 'rush', 'quick']
        urgency_level = 'normal'
        for keyword in urgency_keywords:
            if keyword in description.lower():
                urgency_level = 'high'
                break
        
        # Extract project scope
        scope_indicators = ['small', 'large', 'complex', 'simple', 'ongoing', 'one-time']
        scope = 'medium'
        for indicator in scope_indicators:
            if indicator in description.lower():
                scope = indicator
                break
        
        # Extract collaboration style
        collaboration_keywords = ['team', 'collaborate', 'work together', 'meetings', 'communication']
        collaboration_level = 'standard'
        if any(keyword in description.lower() for keyword in collaboration_keywords):
            collaboration_level = 'high'
        
        return {
            'urgency_level': urgency_level,
            'project_scope': scope,
            'collaboration_level': collaboration_level,
            'description_length': len(description),
            'requirements_clarity': 'high' if len(requirements) > 200 else 'medium' if len(requirements) > 50 else 'low'
        }
    
    def _identify_pain_points(self, job_data: Dict[str, Any], company_research: Optional[CompanyResearch],
                            industry_insights: Optional[IndustryInsights]) -> List[str]:
        """Identify potential client pain points"""
        pain_points = []
        
        # From job description
        description = job_data.get('description', '').lower()
        
        # Common pain point indicators
        pain_indicators = {
            'struggling with': 'Current process inefficiencies',
            'need help': 'Resource constraints',
            'deadline': 'Time pressure',
            'budget': 'Cost concerns',
            'quality': 'Quality issues',
            'scaling': 'Growth challenges',
            'outdated': 'Technology modernization needed',
            'manual': 'Automation opportunities'
        }
        
        for indicator, pain_point in pain_indicators.items():
            if indicator in description:
                pain_points.append(pain_point)
        
        # From company research
        if company_research:
            pain_points.extend(company_research.challenges)
        
        # From industry insights
        if industry_insights:
            pain_points.extend(industry_insights.common_challenges[:2])  # Top 2 challenges
        
        return pain_points[:5]  # Limit to top 5
    
    def _generate_value_propositions(self, job_data: Dict[str, Any], company_research: Optional[CompanyResearch],
                                   industry_insights: Optional[IndustryInsights]) -> List[str]:
        """Generate targeted value propositions"""
        value_props = []
        
        # Base value propositions
        base_props = [
            "Proven track record of delivering high-quality solutions",
            "Deep technical expertise in your industry",
            "Focus on measurable business outcomes",
            "Collaborative approach with clear communication",
            "Commitment to deadlines and project success"
        ]
        
        # Industry-specific value propositions
        if industry_insights:
            if 'technology' in industry_insights.industry_name.lower():
                value_props.append("Cutting-edge technology implementation")
            if 'healthcare' in industry_insights.industry_name.lower():
                value_props.append("HIPAA-compliant solutions with security focus")
            if 'finance' in industry_insights.industry_name.lower():
                value_props.append("Regulatory-compliant financial solutions")
        
        # Company-specific value propositions
        if company_research:
            if company_research.company_size == 'startup':
                value_props.append("Startup-friendly agile development approach")
            elif 'enterprise' in company_research.company_size.lower():
                value_props.append("Enterprise-grade scalability and security")
        
        # Combine and prioritize
        all_props = base_props + value_props
        return all_props[:4]  # Top 4 most relevant
    
    def _extract_relevant_experience(self, job_data: Dict[str, Any], company_research: Optional[CompanyResearch],
                                   industry_insights: Optional[IndustryInsights]) -> List[str]:
        """Extract relevant experience to highlight"""
        relevant_exp = []
        
        # This would typically match against user's profile
        # For now, generate industry-relevant experience examples
        
        if industry_insights:
            industry = industry_insights.industry_name.lower()
            if 'technology' in industry:
                relevant_exp.append("Software development for tech companies")
            if 'healthcare' in industry:
                relevant_exp.append("Healthcare technology solutions")
            if 'finance' in industry:
                relevant_exp.append("Financial services applications")
            if 'ecommerce' in industry:
                relevant_exp.append("E-commerce platform development")
        
        # Company size relevant experience
        if company_research:
            if 'startup' in company_research.company_size.lower():
                relevant_exp.append("Startup technology consulting")
            elif 'enterprise' in company_research.company_size.lower():
                relevant_exp.append("Enterprise software development")
        
        return relevant_exp[:3]  # Top 3 most relevant
    
    async def _generate_talking_points(self, job_data: Dict[str, Any], company_research: Optional[CompanyResearch],
                                     industry_insights: Optional[IndustryInsights]) -> List[str]:
        """Generate custom talking points"""
        try:
            context_data = {
                'job_description': job_data.get('description', ''),
                'company_info': company_research.company_name if company_research else 'Unknown',
                'industry': industry_insights.industry_name if industry_insights else 'Unknown'
            }
            
            talking_points_prompt = f"""
            Generate 3-4 compelling talking points for a freelance proposal based on:
            
            Job: {context_data['job_description'][:500]}
            Company: {context_data['company_info']}
            Industry: {context_data['industry']}
            
            Focus on:
            1. Industry-specific insights
            2. Company-relevant solutions
            3. Unique value propositions
            4. Competitive advantages
            
            Return as JSON array of strings:
            ["talking_point_1", "talking_point_2", "talking_point_3"]
            """
            
            response = await ainvoke_llm(
                system_prompt="You are a business development expert creating compelling talking points for freelance proposals.",
                user_message=talking_points_prompt,
                model=self.config.llm.default_model
            )
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return ["Industry expertise and proven results", "Custom solutions for your specific needs", "Reliable delivery and ongoing support"]
                
        except Exception as e:
            logger.error(f"Error generating talking points: {e}")
            return ["Strong technical expertise", "Proven track record", "Collaborative approach"]
    
    def _determine_tone_adjustments(self, client_analysis: Optional[ClientAnalysisResult],
                                  company_research: Optional[CompanyResearch]) -> Dict[str, str]:
        """Determine tone adjustments based on client and company"""
        tone_adjustments = {
            'formality': 'professional',
            'energy': 'confident',
            'technical_depth': 'moderate'
        }
        
        # Adjust based on client type
        if client_analysis and client_analysis.client_profile:
            if client_analysis.client_profile.risk_level.value == 'low':
                tone_adjustments['formality'] = 'professional'
            elif client_analysis.client_profile.risk_level.value == 'high':
                tone_adjustments['formality'] = 'very_professional'
        
        # Adjust based on company research
        if company_research:
            if 'startup' in company_research.company_size.lower():
                tone_adjustments['energy'] = 'enthusiastic'
                tone_adjustments['formality'] = 'casual_professional'
            elif 'enterprise' in company_research.company_size.lower():
                tone_adjustments['formality'] = 'formal'
                tone_adjustments['technical_depth'] = 'detailed'
        
        return tone_adjustments
    
    def _extract_industry_terminology(self, industry_insights: Optional[IndustryInsights]) -> List[str]:
        """Extract relevant industry terminology"""
        if not industry_insights:
            return []
        
        terminology = []
        
        # From key technologies
        terminology.extend(industry_insights.key_technologies[:3])
        
        # From success metrics
        terminology.extend(industry_insights.success_metrics[:2])
        
        # From market trends
        terminology.extend(industry_insights.market_trends[:2])
        
        return terminology[:5]  # Top 5 terms
    
    def _generate_company_keywords(self, company_research: Optional[CompanyResearch]) -> List[str]:
        """Generate company-specific keywords"""
        if not company_research:
            return []
        
        keywords = []
        
        # From key services
        keywords.extend(company_research.key_services[:3])
        
        # From technologies used
        keywords.extend(company_research.technologies_used[:3])
        
        # From business model
        if company_research.business_model != 'Unknown':
            keywords.append(company_research.business_model)
        
        # From target market
        if company_research.target_market != 'Unknown':
            keywords.append(company_research.target_market)
        
        return keywords[:5]  # Top 5 keywords
    
    def _identify_competitive_advantages(self, job_data: Dict[str, Any], company_research: Optional[CompanyResearch],
                                       industry_insights: Optional[IndustryInsights]) -> List[str]:
        """Identify competitive advantages to highlight"""
        advantages = []
        
        # Base advantages
        base_advantages = [
            "Specialized industry expertise",
            "Proven delivery methodology",
            "Direct communication and collaboration",
            "Flexible and responsive approach"
        ]
        
        # Industry-specific advantages
        if industry_insights:
            if len(industry_insights.key_technologies) > 0:
                advantages.append(f"Expert in {industry_insights.key_technologies[0]}")
            if len(industry_insights.best_practices) > 0:
                advantages.append(f"Follows {industry_insights.best_practices[0]}")
        
        # Company-specific advantages
        if company_research:
            if company_research.growth_stage == 'startup':
                advantages.append("Startup-friendly pricing and approach")
            elif company_research.growth_stage == 'enterprise':
                advantages.append("Enterprise-scale solution experience")
        
        # Combine and prioritize
        all_advantages = base_advantages + advantages
        return all_advantages[:4]  # Top 4 advantages
    
    def _generate_positioning_strategy(self, client_analysis: Optional[ClientAnalysisResult],
                                     company_research: Optional[CompanyResearch],
                                     personalization_level: PersonalizationLevel) -> str:
        """Generate positioning strategy"""
        if personalization_level == PersonalizationLevel.PREMIUM:
            return "Premium expert consultant positioning"
        elif personalization_level == PersonalizationLevel.ADVANCED:
            return "Specialized industry expert positioning"
        elif personalization_level == PersonalizationLevel.STANDARD:
            return "Professional service provider positioning"
        else:
            return "Competitive freelancer positioning"
    
    def _generate_pricing_strategy(self, client_analysis: Optional[ClientAnalysisResult],
                                 company_research: Optional[CompanyResearch],
                                 job_data: Dict[str, Any]) -> str:
        """Generate pricing strategy recommendation"""
        if client_analysis and client_analysis.client_profile:
            if client_analysis.client_profile.avg_project_value > 5000:
                return "Premium value-based pricing"
            elif client_analysis.client_profile.avg_project_value > 2000:
                return "Competitive market-rate pricing"
            else:
                return "Volume-based or package pricing"
        
        return "Standard competitive pricing"

# Global personalization engine
personalization_engine = DynamicPersonalizationEngine()

# Convenience function
async def create_personalized_context(job_data: Dict[str, Any], 
                                    client_analysis: Optional[ClientAnalysisResult] = None,
                                    personalization_level: PersonalizationLevel = PersonalizationLevel.STANDARD) -> PersonalizationContext:
    """Create personalized proposal context"""
    return await personalization_engine.personalize_proposal(job_data, client_analysis, personalization_level)