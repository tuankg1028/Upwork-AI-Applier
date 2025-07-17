import json
import asyncio
import base64
import io
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from .logger import logger, TimedOperation
from .error_handler import with_retry, ErrorContext
from .config import get_config
from .utils import ainvoke_llm

class VisualType(Enum):
    """Types of visual elements that can be generated"""
    TIMELINE = "timeline"
    INFOGRAPHIC = "infographic"
    CHART = "chart"
    PROCESS_FLOW = "process_flow"
    COMPARISON = "comparison"
    SKILLS_MATRIX = "skills_matrix"
    PROJECT_ROADMAP = "project_roadmap"

class ChartType(Enum):
    """Types of charts that can be generated"""
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    PIE_CHART = "pie_chart"
    SCATTER_PLOT = "scatter_plot"
    HEATMAP = "heatmap"
    RADAR_CHART = "radar_chart"

@dataclass
class VisualElement:
    """Represents a visual element for proposals"""
    element_id: str
    visual_type: VisualType
    title: str
    description: str
    data: Dict[str, Any]
    image_data: Optional[str]  # Base64 encoded image
    markdown_representation: str
    integration_text: str
    created_at: datetime

@dataclass
class VisualPackage:
    """Package of visual elements for a proposal"""
    job_id: str
    elements: List[VisualElement]
    total_elements: int
    recommended_placement: Dict[str, str]
    integration_instructions: str
    generated_at: datetime

class TimelineGenerator:
    """Generates project timeline visuals"""
    
    def __init__(self):
        self.config = get_config()
        
    async def generate_project_timeline(self, job_data: Dict[str, Any], 
                                      project_phases: List[Dict[str, Any]]) -> VisualElement:
        """Generate a project timeline visual"""
        
        with TimedOperation("timeline_generation"):
            # Create figure
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Prepare timeline data
            phases = []
            start_date = datetime.now()
            
            for i, phase in enumerate(project_phases):
                duration = phase.get('duration_days', 7)
                end_date = start_date + timedelta(days=duration)
                
                phases.append({
                    'name': phase.get('name', f'Phase {i+1}'),
                    'start': start_date,
                    'end': end_date,
                    'duration': duration,
                    'color': plt.cm.Set3(i / len(project_phases))
                })
                
                start_date = end_date
            
            # Draw timeline
            y_pos = 0
            for i, phase in enumerate(phases):
                # Draw phase bar
                width = phase['duration']
                rect = patches.Rectangle((i * 10, y_pos), width, 0.8, 
                                       facecolor=phase['color'], 
                                       edgecolor='black', linewidth=1)
                ax.add_patch(rect)
                
                # Add phase name
                ax.text(i * 10 + width/2, y_pos + 0.4, phase['name'], 
                       ha='center', va='center', fontsize=10, fontweight='bold')
                
                # Add duration
                ax.text(i * 10 + width/2, y_pos - 0.3, f"{phase['duration']} days", 
                       ha='center', va='center', fontsize=8)
            
            # Formatting
            ax.set_xlim(-1, len(phases) * 10 + 5)
            ax.set_ylim(-1, 2)
            ax.set_title(f"Project Timeline - {job_data.get('title', 'Project')}", 
                        fontsize=16, fontweight='bold', pad=20)
            ax.axis('off')
            
            # Add total duration
            total_duration = sum(p['duration'] for p in phases)
            ax.text(len(phases) * 5, 1.5, f"Total Duration: {total_duration} days", 
                   ha='center', va='center', fontsize=12, 
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue"))
            
            # Convert to base64
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
            img_buffer.seek(0)
            img_data = base64.b64encode(img_buffer.read()).decode()
            plt.close()
            
            # Create markdown representation
            markdown_rep = self._create_timeline_markdown(phases, total_duration)
            
            # Create integration text
            integration_text = f"""
## Project Timeline

I've created a detailed project timeline that breaks down the work into {len(phases)} strategic phases over {total_duration} days. This approach ensures:

- **Clear milestone tracking** with defined deliverables
- **Predictable progress** with regular check-ins
- **Flexible adaptation** to any changes in requirements
- **Quality assurance** built into each phase

The timeline demonstrates my systematic approach to project management and commitment to delivering on schedule.
"""
            
            return VisualElement(
                element_id=f"timeline_{job_data.get('job_id', 'unknown')}",
                visual_type=VisualType.TIMELINE,
                title=f"Project Timeline - {job_data.get('title', 'Project')}",
                description=f"Detailed {len(phases)}-phase timeline spanning {total_duration} days",
                data={
                    'phases': [{'name': p['name'], 'duration': p['duration']} for p in phases],
                    'total_duration': total_duration,
                    'methodology': 'Agile iterative approach'
                },
                image_data=img_data,
                markdown_representation=markdown_rep,
                integration_text=integration_text,
                created_at=datetime.now()
            )
    
    def _create_timeline_markdown(self, phases: List[Dict], total_duration: int) -> str:
        """Create markdown representation of timeline"""
        markdown = "## Project Timeline\n\n"
        
        for i, phase in enumerate(phases, 1):
            markdown += f"**Phase {i}: {phase['name']}** ({phase['duration']} days)\n"
            markdown += f"- Start: {phase['start'].strftime('%Y-%m-%d')}\n"
            markdown += f"- End: {phase['end'].strftime('%Y-%m-%d')}\n\n"
        
        markdown += f"**Total Project Duration:** {total_duration} days\n"
        return markdown

class InfographicGenerator:
    """Generates infographic visuals for proposals"""
    
    def __init__(self):
        self.config = get_config()
        
    async def generate_skills_infographic(self, skills_data: Dict[str, float], 
                                        job_requirements: str) -> VisualElement:
        """Generate a skills match infographic"""
        
        with TimedOperation("infographic_generation"):
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # Prepare data
            skills = list(skills_data.keys())[:8]  # Top 8 skills
            values = [skills_data[skill] for skill in skills]
            
            # Create color gradient
            colors = plt.cm.viridis(np.linspace(0, 1, len(skills)))
            
            # Create horizontal bar chart
            y_pos = np.arange(len(skills))
            bars = ax.barh(y_pos, values, color=colors, alpha=0.8)
            
            # Add value labels
            for i, (bar, value) in enumerate(zip(bars, values)):
                ax.text(value + 1, i, f'{value:.0f}%', 
                       va='center', ha='left', fontweight='bold')
            
            # Formatting
            ax.set_yticks(y_pos)
            ax.set_yticklabels(skills)
            ax.set_xlabel('Proficiency Level (%)', fontsize=12)
            ax.set_title('Skills Match Analysis', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlim(0, 100)
            
            # Add grid
            ax.grid(axis='x', alpha=0.3)
            
            # Add average line
            avg_score = sum(values) / len(values)
            ax.axvline(x=avg_score, color='red', linestyle='--', alpha=0.7, 
                      label=f'Average: {avg_score:.1f}%')
            ax.legend()
            
            # Convert to base64
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
            img_buffer.seek(0)
            img_data = base64.b64encode(img_buffer.read()).decode()
            plt.close()
            
            # Create markdown representation
            markdown_rep = self._create_skills_markdown(skills_data, avg_score)
            
            # Create integration text
            integration_text = f"""
## Skills Alignment Analysis

My skills analysis shows an {avg_score:.1f}% average match with your requirements. Here's what this means:

**Top Strengths:**
- {skills[0]}: {values[0]:.0f}% proficiency
- {skills[1]}: {values[1]:.0f}% proficiency  
- {skills[2]}: {values[2]:.0f}% proficiency

This strong alignment ensures I can deliver quality results while minimizing the learning curve and project risks.
"""
            
            return VisualElement(
                element_id=f"skills_infographic_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                visual_type=VisualType.INFOGRAPHIC,
                title="Skills Match Analysis",
                description=f"Visual breakdown of {len(skills)} key skills with {avg_score:.1f}% average match",
                data={
                    'skills': skills_data,
                    'average_score': avg_score,
                    'top_skills': skills[:3]
                },
                image_data=img_data,
                markdown_representation=markdown_rep,
                integration_text=integration_text,
                created_at=datetime.now()
            )
    
    def _create_skills_markdown(self, skills_data: Dict[str, float], avg_score: float) -> str:
        """Create markdown representation of skills"""
        markdown = "## Skills Analysis\n\n"
        
        for skill, score in sorted(skills_data.items(), key=lambda x: x[1], reverse=True):
            markdown += f"- **{skill}**: {score:.0f}%\n"
        
        markdown += f"\n**Average Match**: {avg_score:.1f}%\n"
        return markdown

class ChartGenerator:
    """Generates various chart types for proposals"""
    
    def __init__(self):
        self.config = get_config()
        
    async def generate_project_comparison_chart(self, comparison_data: Dict[str, Any]) -> VisualElement:
        """Generate a project comparison chart"""
        
        with TimedOperation("chart_generation"):
            # Create figure
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            # Prepare data
            categories = list(comparison_data.keys())
            my_approach = [comparison_data[cat]['my_approach'] for cat in categories]
            typical_approach = [comparison_data[cat]['typical_approach'] for cat in categories]
            
            # Create comparison bar chart
            x = np.arange(len(categories))
            width = 0.35
            
            bars1 = ax1.bar(x - width/2, my_approach, width, label='My Approach', color='#2E86AB')
            bars2 = ax1.bar(x + width/2, typical_approach, width, label='Typical Approach', color='#A23B72')
            
            # Add value labels
            for bars in [bars1, bars2]:
                for bar in bars:
                    height = bar.get_height()
                    ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                           f'{height:.0f}', ha='center', va='bottom')
            
            # Formatting
            ax1.set_xlabel('Project Aspects')
            ax1.set_ylabel('Score (1-10)')
            ax1.set_title('My Approach vs Typical Approach')
            ax1.set_xticks(x)
            ax1.set_xticklabels(categories, rotation=45, ha='right')
            ax1.legend()
            ax1.grid(axis='y', alpha=0.3)
            
            # Create radar chart for overall comparison
            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
            angles += angles[:1]  # Complete the circle
            
            my_approach_radar = my_approach + [my_approach[0]]
            typical_approach_radar = typical_approach + [typical_approach[0]]
            
            ax2.plot(angles, my_approach_radar, 'o-', linewidth=2, label='My Approach', color='#2E86AB')
            ax2.fill(angles, my_approach_radar, alpha=0.25, color='#2E86AB')
            ax2.plot(angles, typical_approach_radar, 'o-', linewidth=2, label='Typical Approach', color='#A23B72')
            ax2.fill(angles, typical_approach_radar, alpha=0.25, color='#A23B72')
            
            ax2.set_xticks(angles[:-1])
            ax2.set_xticklabels(categories)
            ax2.set_ylim(0, 10)
            ax2.set_title('Comparative Analysis (Radar View)')
            ax2.legend()
            ax2.grid(True)
            
            plt.tight_layout()
            
            # Convert to base64
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
            img_buffer.seek(0)
            img_data = base64.b64encode(img_buffer.read()).decode()
            plt.close()
            
            # Calculate advantages
            advantages = []
            for cat in categories:
                diff = comparison_data[cat]['my_approach'] - comparison_data[cat]['typical_approach']
                if diff > 0:
                    advantages.append(f"{cat}: +{diff:.1f} points")
            
            # Create integration text
            integration_text = f"""
## Competitive Analysis

My approach offers measurable advantages across {len(advantages)} key areas:

{chr(10).join(f"• {adv}" for adv in advantages[:4])}

This data-driven comparison demonstrates why my methodology delivers superior results compared to typical approaches in the market.
"""
            
            return VisualElement(
                element_id=f"comparison_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                visual_type=VisualType.COMPARISON,
                title="Project Approach Comparison",
                description=f"Comparative analysis across {len(categories)} project dimensions",
                data={
                    'categories': categories,
                    'my_scores': my_approach,
                    'typical_scores': typical_approach,
                    'advantages': advantages
                },
                image_data=img_data,
                markdown_representation=self._create_comparison_markdown(comparison_data),
                integration_text=integration_text,
                created_at=datetime.now()
            )
    
    def _create_comparison_markdown(self, comparison_data: Dict[str, Any]) -> str:
        """Create markdown representation of comparison"""
        markdown = "## Project Approach Comparison\n\n"
        markdown += "| Aspect | My Approach | Typical Approach | Advantage |\n"
        markdown += "|--------|-------------|------------------|----------|\n"
        
        for cat, data in comparison_data.items():
            my_score = data['my_approach']
            typical_score = data['typical_approach']
            advantage = my_score - typical_score
            advantage_str = f"+{advantage:.1f}" if advantage > 0 else f"{advantage:.1f}"
            markdown += f"| {cat} | {my_score:.1f} | {typical_score:.1f} | {advantage_str} |\n"
        
        return markdown

class VisualElementsEngine:
    """Main engine for generating visual elements for proposals"""
    
    def __init__(self):
        self.config = get_config()
        self.timeline_generator = TimelineGenerator()
        self.infographic_generator = InfographicGenerator()
        self.chart_generator = ChartGenerator()
        
    @with_retry(operation_name="generate_visual_package")
    async def generate_visual_package(self, job_data: Dict[str, Any],
                                    client_analysis: Any,
                                    scoring_result: Any,
                                    personalization_context: Any,
                                    profile: str) -> VisualPackage:
        """Generate a complete visual package for a proposal"""
        
        with TimedOperation("visual_package_generation"):
            elements = []
            
            try:
                # 1. Generate project timeline
                project_phases = await self._extract_project_phases(job_data, profile)
                if project_phases:
                    timeline = await self.timeline_generator.generate_project_timeline(
                        job_data, project_phases
                    )
                    elements.append(timeline)
                
                # 2. Generate skills infographic
                skills_data = await self._extract_skills_data(job_data, profile)
                if skills_data:
                    skills_infographic = await self.infographic_generator.generate_skills_infographic(
                        skills_data, job_data.get('description', '')
                    )
                    elements.append(skills_infographic)
                
                # 3. Generate comparison chart
                comparison_data = await self._generate_comparison_data(job_data, profile)
                if comparison_data:
                    comparison_chart = await self.chart_generator.generate_project_comparison_chart(
                        comparison_data
                    )
                    elements.append(comparison_chart)
                
                # 4. Generate recommended placement
                placement = self._recommend_visual_placement(elements)
                
                # 5. Generate integration instructions
                integration_instructions = self._generate_integration_instructions(elements)
                
                package = VisualPackage(
                    job_id=job_data.get('job_id', 'unknown'),
                    elements=elements,
                    total_elements=len(elements),
                    recommended_placement=placement,
                    integration_instructions=integration_instructions,
                    generated_at=datetime.now()
                )
                
                logger.info(f"Generated visual package with {len(elements)} elements for job {job_data.get('job_id', 'unknown')}")
                return package
                
            except Exception as e:
                logger.error(f"Error generating visual package: {e}")
                # Return empty package on error
                return VisualPackage(
                    job_id=job_data.get('job_id', 'unknown'),
                    elements=[],
                    total_elements=0,
                    recommended_placement={},
                    integration_instructions="Visual elements generation failed - proceeding with text-only proposal.",
                    generated_at=datetime.now()
                )
    
    async def _extract_project_phases(self, job_data: Dict[str, Any], profile: str) -> List[Dict[str, Any]]:
        """Extract project phases from job description using AI"""
        
        try:
            job_description = job_data.get('description', '')
            
            phase_extraction_prompt = f"""
            Analyze this job description and create a logical project breakdown into phases:
            
            Job Description: {job_description}
            
            Based on the job requirements, create 3-5 project phases with:
            - Phase name
            - Duration in days
            - Key deliverables
            
            Return only a JSON array of phases like:
            [
                {{"name": "Phase Name", "duration_days": 7, "deliverables": ["item1", "item2"]}},
                ...
            ]
            """
            
            response = await ainvoke_llm(
                system_prompt="You are a project management expert. Analyze job descriptions and create logical project phases.",
                user_message=phase_extraction_prompt,
                model=self.config.llm.default_model
            )
            
            phases = json.loads(response)
            return phases if isinstance(phases, list) else []
            
        except Exception as e:
            logger.error(f"Error extracting project phases: {e}")
            return []
    
    async def _extract_skills_data(self, job_data: Dict[str, Any], profile: str) -> Dict[str, float]:
        """Extract skills data and match with job requirements"""
        
        try:
            job_description = job_data.get('description', '')
            
            skills_prompt = f"""
            Analyze the job requirements and rate how well this freelancer profile matches:
            
            Job Description: {job_description}
            Freelancer Profile: {profile[:1000]}
            
            Rate the match for relevant skills (0-100%):
            Return only a JSON object like:
            {{"skill_name": score, "another_skill": score, ...}}
            
            Include 6-8 most relevant skills.
            """
            
            response = await ainvoke_llm(
                system_prompt="You are a skills assessment expert. Rate freelancer skills against job requirements.",
                user_message=skills_prompt,
                model=self.config.llm.default_model
            )
            
            skills = json.loads(response)
            return skills if isinstance(skills, dict) else {}
            
        except Exception as e:
            logger.error(f"Error extracting skills data: {e}")
            return {}
    
    async def _generate_comparison_data(self, job_data: Dict[str, Any], profile: str) -> Dict[str, Any]:
        """Generate comparison data for competitive analysis"""
        
        try:
            comparison_prompt = f"""
            Create a competitive analysis comparing my approach vs typical approaches for this job:
            
            Job Description: {job_data.get('description', '')}
            My Profile: {profile[:800]}
            
            Rate both approaches (1-10) across these dimensions:
            - Quality
            - Speed
            - Communication
            - Innovation
            - Value
            
            Return JSON like:
            {{"Quality": {{"my_approach": 9, "typical_approach": 7}}, ...}}
            """
            
            response = await ainvoke_llm(
                system_prompt="You are a competitive analysis expert. Compare freelancer approaches objectively.",
                user_message=comparison_prompt,
                model=self.config.llm.default_model
            )
            
            comparison = json.loads(response)
            return comparison if isinstance(comparison, dict) else {}
            
        except Exception as e:
            logger.error(f"Error generating comparison data: {e}")
            return {}
    
    def _recommend_visual_placement(self, elements: List[VisualElement]) -> Dict[str, str]:
        """Recommend where to place visual elements in the proposal"""
        
        placement = {}
        
        for element in elements:
            if element.visual_type == VisualType.TIMELINE:
                placement[element.element_id] = "middle"  # After approach description
            elif element.visual_type == VisualType.INFOGRAPHIC:
                placement[element.element_id] = "early"   # After introduction
            elif element.visual_type == VisualType.COMPARISON:
                placement[element.element_id] = "late"    # Before conclusion
            else:
                placement[element.element_id] = "middle"
        
        return placement
    
    def _generate_integration_instructions(self, elements: List[VisualElement]) -> str:
        """Generate instructions for integrating visuals into proposals"""
        
        if not elements:
            return "No visual elements to integrate."
        
        instructions = "## Visual Integration Instructions\n\n"
        
        for element in elements:
            instructions += f"### {element.title}\n"
            instructions += f"- **Placement**: {element.description}\n"
            instructions += f"- **Integration**: {element.integration_text[:200]}...\n"
            instructions += f"- **Format**: Base64 encoded PNG image\n\n"
        
        instructions += f"**Total Elements**: {len(elements)}\n"
        instructions += "**Note**: Include visual elements to enhance proposal impact and demonstrate professionalism.\n"
        
        return instructions

# Global visual elements engine
visual_elements_engine = VisualElementsEngine()

# Convenience functions
async def generate_visual_package(job_data: Dict[str, Any],
                                client_analysis: Any,
                                scoring_result: Any,
                                personalization_context: Any,
                                profile: str) -> VisualPackage:
    """Generate visual package for a proposal"""
    return await visual_elements_engine.generate_visual_package(
        job_data, client_analysis, scoring_result, personalization_context, profile
    )

def integrate_visuals_into_proposal(proposal_text: str, visual_package: VisualPackage) -> str:
    """Integrate visual elements into proposal text"""
    
    if not visual_package.elements:
        return proposal_text
    
    # Add visual elements at appropriate locations
    enhanced_proposal = proposal_text
    
    # Add visual integration note
    visual_note = f"\n\n---\n*This proposal includes {visual_package.total_elements} visual elements to better illustrate my approach and qualifications.*\n"
    enhanced_proposal += visual_note
    
    # Add visual elements
    for element in visual_package.elements:
        enhanced_proposal += f"\n\n{element.integration_text}"
        enhanced_proposal += f"\n\n*[Visual Element: {element.title}]*"
        enhanced_proposal += f"\n{element.markdown_representation}"
    
    return enhanced_proposal