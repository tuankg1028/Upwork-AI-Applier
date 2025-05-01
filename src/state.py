import operator
from typing import Annotated
from typing_extensions import TypedDict

class MainGraphStateInput(TypedDict):
    job_title: str

class MainGraphState(TypedDict):
    job_title: str
    scraped_jobs: list[dict]
    scores: Annotated[list, operator.add]
    jobs_processing_batch: list
    matches: list
    applications: Annotated[list, operator.add]
    
class ScoreJobsState(TypedDict):
    jobs_batch: str
    
class ApplicationStateInput(TypedDict):
    job_description: str
    
class ApplicationState(TypedDict):
    job_description: str
    relevant_infos: str
    cover_letter: str
    interview_prep: str
    applications: Annotated[list, operator.add]