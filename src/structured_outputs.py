from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class JobType(str, Enum):
    FIXED = "Fixed"
    HOURLY = "Hourly"

class ClientInformation(BaseModel):
    joined_date: str = Field(description="The date the client joined the platform")
    location: str = Field(description="The client's location")
    total_spent: str = Field(description="The total amount spent by the client ($)") 
    total_hires: int = Field(description="The total number of hires by the client") 
    company_profile: Optional[str] = Field(
        description="The client's company profile or description"
    ) 

class JobInformation(BaseModel):
    title: str = Field(description="The title of the job")
    description: str = Field(description="The original full job description, must be extracted without any summarization or omission.")
    job_type: JobType = Field(description="The type of the job (Fixed or Hourly)")
    experience_level: str = Field(description="The experience level required for the job")
    duration: str = Field(description="The duration of the job")
    payment_rate: Optional[str] = Field(
        description="""
        The payment rate for the job. Can be in several formats:
        - Hourly rate range: '$15.00-$25.00' or '$15-$25'
        - Fixed rate: '$500' or '$1,000'
        - Budget range: '$500-$1,000'
        All values should include the '$' symbol.
        """
    )
    client_information: Optional[ClientInformation] = Field(
        description="The description of the client including location, number of hires, total spent, etc."
    )
    proposal_requirements: Optional[str] = Field(
        description="Notes left by the client regarding the proposal requiremenets. For example, instructions or special requests such as 'Begin your proposal with "" to confirm you’ve read the full posting.'"
    )
    
class JobScore(BaseModel):
    job_id: str = Field(description="The id of the job")
    score: int = Field(description="The score of the job")

class JobScores(BaseModel):
    scores: List[JobScore] = Field(description="The list of job scores")
    
class CoverLetter(BaseModel):
    letter: str = Field(description="The generated cover letter")
    
class CallScript(BaseModel):
    script: str = Field(description="The generated call script")
     
class JobApplication(BaseModel):
    job_description: str = Field(description="The full description of the job")
    cover_letter: str = Field(description="The generated cover letter")
    interview_preparation: str = Field(description="The generated interview preparation")
    metadata: Optional[Dict[str, Any]] = Field(description="Additional metadata about the application", default=None)
    quality_score: Optional[float] = Field(description="Quality score of the application", default=None)
    visual_elements_count: Optional[int] = Field(description="Number of visual elements included", default=0)