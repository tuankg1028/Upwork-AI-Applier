#!/usr/bin/env python3
"""
Enhanced Upwork AI Applier Workflow Demo

This script demonstrates the complete enhanced workflow with all Phase 2 and Phase 3 features:
- Dynamic proposal personalization
- Multi-version content generation
- Visual elements integration
- Advanced quality assurance
- Smart follow-up system
- Calendar integration

Usage:
    python src/enhanced_workflow_demo.py --demo
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any

from .config import get_config
from .logger import logger
from .client_intelligence import analyze_client_success
from .enhanced_scoring import create_enhanced_scorer
from .dynamic_personalization import create_personalization_engine
from .multi_version_generator import generate_content_versions
from .visual_elements import generate_visual_package
from .advanced_quality_assurance import comprehensive_quality_assessment
from .smart_followup import create_followup_strategy
from .calendar_integration import create_application_calendar, export_calendar_to_ical

class EnhancedWorkflowDemo:
    """Demonstrates the complete enhanced workflow"""
    
    def __init__(self):
        self.config = get_config()
        self.profile = self._load_demo_profile()
        self.enhanced_scorer = create_enhanced_scorer(self.profile)
        self.personalization_engine = create_personalization_engine()
        
    def _load_demo_profile(self) -> str:
        """Load demo freelancer profile"""
        return """
        I am a Senior Full-Stack Developer with 8+ years of experience in building scalable web applications.
        
        Technical Skills:
        - Frontend: React, Vue.js, Angular, TypeScript, JavaScript, HTML5, CSS3
        - Backend: Node.js, Python, Django, Flask, Express.js
        - Databases: PostgreSQL, MySQL, MongoDB, Redis
        - Cloud: AWS, Google Cloud, Azure
        - DevOps: Docker, Kubernetes, CI/CD, Jenkins
        - Mobile: React Native, Flutter
        
        Recent Projects:
        - Built a real-time collaboration platform serving 10,000+ users
        - Developed an AI-powered analytics dashboard for Fortune 500 company
        - Created a mobile app with 50,000+ downloads
        - Implemented microservices architecture reducing load time by 60%
        
        Expertise:
        - Performance optimization
        - System architecture design
        - API development and integration
        - Database optimization
        - Team leadership and mentoring
        
        I deliver high-quality code, meet deadlines consistently, and communicate effectively with clients.
        """
    
    def _get_demo_job_data(self) -> Dict[str, Any]:
        """Get demo job data"""
        return {
            'job_id': 'demo_job_001',
            'title': 'Senior React Developer for E-commerce Platform',
            'description': """
            We are looking for an experienced React developer to join our team and help build a modern e-commerce platform.
            
            Requirements:
            - 5+ years of React experience
            - Strong TypeScript skills
            - Experience with state management (Redux/Context API)
            - Knowledge of modern CSS frameworks
            - Experience with testing (Jest, React Testing Library)
            - Familiar with REST APIs and GraphQL
            - Experience with e-commerce platforms preferred
            
            Project Details:
            - Build responsive product catalog
            - Implement shopping cart and checkout flow
            - Integrate payment processing
            - Optimize for performance and SEO
            - Timeline: 8-12 weeks
            - Budget: $15,000-25,000
            
            We're a growing startup in the sustainable fashion space, looking to revolutionize how people shop for eco-friendly clothing.
            """,
            'payment_rate': '$50-75/hr',
            'experience_level': 'Expert',
            'job_type': 'Hourly',
            'duration': '3-6 months',
            'client_total_spent': '$125,000',
            'client_total_hires': 15,
            'client_location': 'San Francisco, CA',
            'client_joined_date': 'March 2020',
            'client_company_profile': 'GreenFashion Co. - We are a sustainable fashion startup focused on eco-friendly clothing and ethical manufacturing practices.',
            'proposal_requirements': 'Please start your proposal with "SUSTAINABLE FASHION" to show you have read the full posting.'
        }
    
    async def run_complete_workflow(self) -> Dict[str, Any]:
        """Run the complete enhanced workflow"""
        
        print("🚀 Starting Enhanced Upwork AI Applier Workflow Demo")
        print("=" * 60)
        
        # Step 1: Load job data
        print("\n📋 Step 1: Loading job data...")
        job_data = self._get_demo_job_data()
        print(f"✓ Job: {job_data['title']}")
        print(f"✓ Budget: {job_data['payment_rate']}")
        print(f"✓ Client: {job_data['client_location']}")
        
        # Step 2: Client intelligence analysis
        print("\n🧠 Step 2: Client intelligence analysis...")
        client_analysis = await analyze_client_success(job_data, {'description': job_data['description']})
        print(f"✓ Client success probability: {client_analysis.client_profile.success_probability:.1f}%")
        print(f"✓ Client risk level: {client_analysis.client_profile.risk_level.value}")
        print(f"✓ Payment reliability: {client_analysis.client_profile.payment_reliability:.1f}%")
        
        # Step 3: Enhanced job scoring
        print("\n📊 Step 3: Enhanced job scoring...")
        scoring_result = await self.enhanced_scorer.score_job(job_data)
        print(f"✓ Overall score: {scoring_result.overall_score:.1f}/100")
        print(f"✓ Confidence: {scoring_result.confidence.value}")
        print(f"✓ Top strength: {scoring_result.strengths[0] if scoring_result.strengths else 'Good overall match'}")
        
        # Step 4: Dynamic personalization
        print("\n🎯 Step 4: Dynamic personalization...")
        personalization_context = await self.personalization_engine.create_personalization_context(
            job_data, client_analysis, scoring_result
        )
        print(f"✓ Company research: {personalization_context.company_research.company_name}")
        print(f"✓ Industry: {personalization_context.company_research.industry}")
        print(f"✓ Key insights: {len(personalization_context.company_research.key_insights)} discovered")
        
        # Step 5: Multi-version content generation
        print("\n📝 Step 5: Multi-version content generation...")
        version_results = await generate_content_versions(
            job_data, client_analysis, scoring_result, personalization_context, self.profile
        )
        print(f"✓ Generated {len(version_results.alternative_versions) + 1} versions")
        print(f"✓ Recommended version: {version_results.recommended_version}")
        print(f"✓ A/B testing ready: {version_results.ab_test_ready}")
        
        # Step 6: Visual elements generation
        print("\n🎨 Step 6: Visual elements generation...")
        visual_package = await generate_visual_package(
            job_data, client_analysis, scoring_result, personalization_context, self.profile
        )
        print(f"✓ Generated {visual_package.total_elements} visual elements")
        if visual_package.elements:
            for element in visual_package.elements:
                print(f"  - {element.visual_type.value}: {element.title}")
        
        # Step 7: Advanced quality assurance
        print("\n🔍 Step 7: Advanced quality assurance...")
        best_proposal = version_results.primary_version.content
        quality_assessment = await comprehensive_quality_assessment(
            best_proposal, job_data['description'], self.profile, 
            personalization_context.company_research.company_name
        )
        print(f"✓ Quality score: {quality_assessment.overall_score:.1f}/100")
        print(f"✓ Quality level: {quality_assessment.overall_level.value}")
        print(f"✓ Confidence: {quality_assessment.confidence:.1f}%")
        if quality_assessment.strengths:
            print(f"✓ Key strength: {quality_assessment.strengths[0]}")
        
        # Step 8: Smart follow-up strategy
        print("\n📅 Step 8: Smart follow-up strategy...")
        application_data = {
            'quality_score': quality_assessment.overall_score,
            'quality_level': quality_assessment.overall_level.value,
            'visual_elements_count': visual_package.total_elements,
            'version_metadata': {
                'version_type': version_results.primary_version.version.value,
                'strategy': version_results.primary_version.strategy.value
            }
        }
        
        followup_strategy = await create_followup_strategy(
            job_data, client_analysis, application_data
        )
        print(f"✓ Created {followup_strategy.total_actions} follow-up actions")
        print(f"✓ Estimated success rate: {followup_strategy.estimated_success_rate:.1f}%")
        
        # Step 9: Calendar integration
        print("\n📆 Step 9: Calendar integration...")
        calendar_schedule = await create_application_calendar(
            [application_data], [followup_strategy], days_ahead=30
        )
        print(f"✓ Created calendar with {calendar_schedule.total_events} events")
        print(f"✓ High priority events: {calendar_schedule.high_priority_events}")
        if calendar_schedule.conflicts:
            print(f"⚠ Conflicts detected: {len(calendar_schedule.conflicts)}")
        
        # Step 10: Export calendar
        print("\n💾 Step 10: Export results...")
        ical_filename = await export_calendar_to_ical(calendar_schedule)
        if ical_filename:
            print(f"✓ Calendar exported to: {ical_filename}")
        
        # Compile results
        results = {
            'job_data': job_data,
            'client_analysis': {
                'success_probability': client_analysis.client_profile.success_probability,
                'risk_level': client_analysis.client_profile.risk_level.value,
                'recommendations': client_analysis.recommendations
            },
            'scoring_result': {
                'overall_score': scoring_result.overall_score,
                'confidence': scoring_result.confidence.value,
                'strengths': scoring_result.strengths,
                'weaknesses': scoring_result.weaknesses
            },
            'personalization': {
                'company_name': personalization_context.company_research.company_name,
                'industry': personalization_context.company_research.industry,
                'key_insights': personalization_context.company_research.key_insights
            },
            'content_versions': {
                'total_versions': len(version_results.alternative_versions) + 1,
                'recommended_version': version_results.recommended_version,
                'ab_test_ready': version_results.ab_test_ready
            },
            'visual_elements': {
                'total_elements': visual_package.total_elements,
                'element_types': [e.visual_type.value for e in visual_package.elements]
            },
            'quality_assessment': {
                'overall_score': quality_assessment.overall_score,
                'quality_level': quality_assessment.overall_level.value,
                'confidence': quality_assessment.confidence,
                'strengths': quality_assessment.strengths,
                'recommendations': quality_assessment.recommendations
            },
            'followup_strategy': {
                'total_actions': followup_strategy.total_actions,
                'estimated_success_rate': followup_strategy.estimated_success_rate,
                'action_types': [action.followup_type.value for action in followup_strategy.timeline]
            },
            'calendar_schedule': {
                'total_events': calendar_schedule.total_events,
                'high_priority_events': calendar_schedule.high_priority_events,
                'conflicts': calendar_schedule.conflicts,
                'recommendations': calendar_schedule.recommendations
            }
        }
        
        print("\n🎉 Enhanced Workflow Complete!")
        print("=" * 60)
        print(f"✅ Generated high-quality proposal with {quality_assessment.overall_score:.1f}/100 score")
        print(f"✅ Created {followup_strategy.total_actions}-step follow-up strategy")
        print(f"✅ Scheduled {calendar_schedule.total_events} calendar events")
        print(f"✅ Integrated {visual_package.total_elements} visual elements")
        print(f"✅ Estimated success probability: {client_analysis.client_profile.success_probability:.1f}%")
        
        return results
    
    def generate_summary_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive summary report"""
        
        report = f"""
# Enhanced Upwork AI Applier - Workflow Summary Report

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Job Analysis
- **Job Title**: {results['job_data']['title']}
- **Budget**: {results['job_data']['payment_rate']}
- **Client Location**: {results['job_data']['client_location']}
- **Experience Level**: {results['job_data']['experience_level']}

## Client Intelligence
- **Success Probability**: {results['client_analysis']['success_probability']:.1f}%
- **Risk Level**: {results['client_analysis']['risk_level']}
- **Key Recommendations**: {len(results['client_analysis']['recommendations'])} generated

## Enhanced Scoring
- **Overall Score**: {results['scoring_result']['overall_score']:.1f}/100
- **Confidence Level**: {results['scoring_result']['confidence']}
- **Strengths**: {len(results['scoring_result']['strengths'])} identified
- **Areas for Improvement**: {len(results['scoring_result']['weaknesses'])} identified

## Dynamic Personalization
- **Company**: {results['personalization']['company_name']}
- **Industry**: {results['personalization']['industry']}
- **Research Insights**: {len(results['personalization']['key_insights'])} discovered

## Content Generation
- **Total Versions**: {results['content_versions']['total_versions']}
- **A/B Testing Ready**: {results['content_versions']['ab_test_ready']}
- **Recommended Version**: {results['content_versions']['recommended_version']}

## Visual Elements
- **Total Elements**: {results['visual_elements']['total_elements']}
- **Element Types**: {', '.join(results['visual_elements']['element_types'])}

## Quality Assessment
- **Quality Score**: {results['quality_assessment']['overall_score']:.1f}/100
- **Quality Level**: {results['quality_assessment']['quality_level']}
- **Assessment Confidence**: {results['quality_assessment']['confidence']:.1f}%
- **Key Strengths**: {len(results['quality_assessment']['strengths'])} identified
- **Recommendations**: {len(results['quality_assessment']['recommendations'])} provided

## Follow-up Strategy
- **Total Actions**: {results['followup_strategy']['total_actions']}
- **Estimated Success Rate**: {results['followup_strategy']['estimated_success_rate']:.1f}%
- **Action Types**: {', '.join(set(results['followup_strategy']['action_types']))}

## Calendar Integration
- **Total Events**: {results['calendar_schedule']['total_events']}
- **High Priority Events**: {results['calendar_schedule']['high_priority_events']}
- **Conflicts**: {len(results['calendar_schedule']['conflicts'])}
- **Recommendations**: {len(results['calendar_schedule']['recommendations'])}

## Summary
This enhanced workflow demonstrates the complete AI-powered job application system with:

1. **Intelligent Analysis**: Deep client and job analysis with predictive scoring
2. **Dynamic Personalization**: Company research and industry-specific insights
3. **Multi-Version Generation**: A/B testing capabilities with strategic variations
4. **Visual Enhancement**: Professional charts, timelines, and infographics
5. **Quality Assurance**: Comprehensive quality assessment with actionable feedback
6. **Smart Follow-up**: Automated follow-up strategy with optimal timing
7. **Calendar Integration**: Seamless scheduling and deadline management

The system achieved a **{results['quality_assessment']['overall_score']:.1f}/100** quality score with **{results['client_analysis']['success_probability']:.1f}%** estimated success probability.
"""
        
        return report

async def main():
    """Main demo function"""
    demo = EnhancedWorkflowDemo()
    
    try:
        # Run the complete workflow
        results = await demo.run_complete_workflow()
        
        # Generate summary report
        report = demo.generate_summary_report(results)
        
        # Save report
        with open('enhanced_workflow_report.md', 'w') as f:
            f.write(report)
        
        print(f"\n📊 Summary report saved to: enhanced_workflow_report.md")
        
        # Save detailed results
        with open('enhanced_workflow_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"📋 Detailed results saved to: enhanced_workflow_results.json")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())