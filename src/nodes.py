from datetime import datetime
from langgraph.constants import Send
from typing import List
from colorama import Fore, Style
from .scraper import UpworkJobScraper
from .utils import (
    ainvoke_llm,
    format_scraped_job_for_scoring,
    convert_jobs_matched_to_string_list,
    COVER_LETTERS_FILE
)
from .structured_outputs import (
    JobScores,
    CoverLetter,
    CallScript,
    JobApplication
)
from .database import ensure_db_exists, save_jobs
from .state import *
from .prompts import *

class MainGraphNodes:
    def __init__(self, profile, num_jobs=10, batch_size=3):
        self.profile = profile
        self.number_of_jobs = num_jobs
        self.batch_size = batch_size
        self.upwork_scraper = UpworkJobScraper()
        
        # Ensure jobs DB exists or create it
        ensure_db_exists()

    async def scrape_upwork_jobs(self, state: MainGraphState):
        """
        Scrape jobs based on job title provided.

        @param state: The current state of the application.
        @return: Updated state with scraped jobs.
        """
        job_title = state["job_title"]

        print(
            Fore.YELLOW
            + f"----- Scraping Upwork jobs for: {job_title} -----\n"
            + Style.RESET_ALL
        )
        job_listings = await self.upwork_scraper.scrape_upwork_data(job_title, self.number_of_jobs)

        print(
            Fore.GREEN
            + f"----- Scraped {len(job_listings)} jobs -----\n"
            + Style.RESET_ALL
        )
        return {**state, "scraped_jobs": job_listings}

    def initiate_jobs_scoring(self, state: MainGraphState) -> List[Send]:
        """
        Divide the scraped jobs into batches for parallel processing.

        @param state: The current state with scraped jobs.
        @return: A list of Send operations, one for each batch.
        """
        jobs = state["scraped_jobs"]
        batches = [
            jobs[i : i + self.batch_size]
            for i in range(0, len(jobs), self.batch_size)
        ]
        return [
            Send("score_scraped_jobs", ScoreJobsState(jobs_batch=batch))
            for batch in batches
        ]

    async def score_scraped_jobs(self, state: ScoreJobsState) -> MainGraphState:
        """
        Score a batch of jobs using an LLM.

        @param state: The current state with a batch of jobs.
        @return: Updated state with scored jobs.
        """
        print(Fore.YELLOW + "----- Scoring a batch of jobs -----\n" + Style.RESET_ALL)
        jobs_list = format_scraped_job_for_scoring(state["jobs_batch"])
        score_jobs_prompt = SCORE_JOBS_PROMPT.format(profile=self.profile)
        results = await ainvoke_llm(
            system_prompt=score_jobs_prompt,
            user_message=f"Evaluate these Jobs:\n\n{jobs_list}",
            model="openai/gpt-4o-mini",
            response_format=JobScores
        )
        jobs_scores = results.model_dump()
        return {"scores": [*jobs_scores["scores"]]}

    def check_for_job_matches(self, state):
        """
        Check and process job matches based on scores.

        @param state: Current application state.
        @return: Updated state with job matches and scores.
        """
        print(
            Fore.YELLOW
            + "----- Checking for remaining job matches -----\n"
            + Style.RESET_ALL
        )
        all_jobs = state["scraped_jobs"]
        
        # Add scores to jobs
        all_jobs = [job | {"score": score["score"]} for job, score in zip(all_jobs, state["scores"])]
        print(all_jobs)
        
        jobs_matched = [job for job in all_jobs if job["score"] >= 7]
        
        # Save matched jobs details to DB
        save_jobs(all_jobs)
        
        # Convert jobs to list of string for easy LLM readability
        matches = convert_jobs_matched_to_string_list(jobs_matched)

        return {
            "scraped_jobs": all_jobs,
            "matches": matches
        }

    def need_to_process_matches(self, state):
        """
        Determine if job matches need further processing.

        @param state: Current application state.
        @return: String indicating processing requirement.
        """
        jobs_matched_count = len(state["matches"])
        if jobs_matched_count == 0:
            print(Fore.RED + "No job matches remaining\n" + Style.RESET_ALL)
            return "No matches"
        else:
            print(
                Fore.GREEN
                + f"There are {jobs_matched_count} job matches remaining to process\n"
                + Style.RESET_ALL
            )
            return "Process jobs"

    def generate_jobs_applications(self, state):
        """
        Calculate the batch of jobs to process and remove them from the matches list.

        @param state: Current application state.
        @return: List of jobs in the current batch.
        """
        print(
            Fore.YELLOW
            + "----- Generating Jobs Applications -----\n"
            + Style.RESET_ALL
        )
        # Calculate the batch of jobs to process
        job_matched = state["matches"]
        batch = job_matched[:self.batch_size]
        job_matched = job_matched[self.batch_size:]  # Remove processed jobs
        
        return {
            "matches": job_matched,
            "jobs_processing_batch": batch
        }

    def initiate_content_generation(self, state: MainGraphState) -> List[Send]:
        """
        Start generating job application content in parallel.

        @param state: Current application state with matches.
        @return: List of Send operations for content generation.
        """
        return [
            Send("create_job_application_content", {"job_description": job})
            for job in state["jobs_processing_batch"]
        ]

    def save_generated_jobs_application(self, state: MainGraphState):
        """
        Save the generated job applications to a file.

        @param state: Current application state with applications.
        @return: Unchanged state.
        """
        print(
            Fore.YELLOW + "----- Saving Generated Job Applications content -----\n" + Style.RESET_ALL
        )
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(COVER_LETTERS_FILE, "a") as file:
            file.write("\n" + "=" * 80 + "\n")
            file.write(f"DATE: {timestamp}\n")
            file.write("=" * 80 + "\n\n")

            for application in state["applications"]:
                file.write("### Job Description\n")
                file.write(application.job_description + "\n\n")

                file.write("### Cover Letter\n")
                file.write(application.cover_letter + "\n\n")

                file.write("### Interview Preparation\n")
                file.write(application.interview_preparation + "\n\n")

                file.write("\n" + "/" * 100 + "\n")

        return state

class CreateJobApplicationNodes:
    def __init__(self, profile):
        self.profile = profile

    async def gather_relevant_infos_from_profile(self, state: ApplicationState):
        """
        Gather relevant information from the freelancer profile.

        @param state: Current application state.
        @return: Updated state with relevant information.
        """
        print(Fore.YELLOW + "----- Gathering Relevant Information from Profile -----\n" + Style.RESET_ALL)
        profile_analysis_prompt = PROFILE_ANALYZER_PROMPT.format(profile=self.profile)
        information = await ainvoke_llm(
            system_prompt=profile_analysis_prompt,
            user_message=state["job_description"],
            model="openai/gpt-4o-mini"
        )
        return {"relevant_infos": information}

    async def generate_cover_letter(self, state: ApplicationState):
        """
        Generate a cover letter based on job description and profile.

        @param state: Current application state.
        @return: Updated state with generated cover letter.
        """
        print(Fore.YELLOW + "----- Generating Cover Letter -----\n" + Style.RESET_ALL)
        cover_letter_prompt = GENERATE_COVER_LETTER_PROMPT.format(
            profile=state["relevant_infos"]
        )
        result = await ainvoke_llm(
            system_prompt=cover_letter_prompt,
            user_message=f"Write a cover letter for the job described below:\n\n{state['job_description']}",
            model="openai/gpt-4o-mini",
            response_format=CoverLetter
        )
        return {"cover_letter": result.letter}

    async def generate_interview_preparation(self, state: ApplicationState):
        """
        Generate the job interview preparation script based on job description and profile.
        """
        print(Fore.YELLOW + "----- Generating Interview Preparation -----\n" + Style.RESET_ALL)
        interview_preparation_prompt = GENERATE_INTERVIEW_PREPARATION_PROMPT.format(profile=state["relevant_infos"])
        result = await ainvoke_llm(
            system_prompt=interview_preparation_prompt,
            user_message=f"Create preparation for the job described below:\n\n{state['job_description']}",
            model="openai/gpt-4o-mini",
            response_format=CallScript
        )
        return {"interview_prep": result.script}
    
    def finalize_job_application(self, state: ApplicationState): 
        """
        Saves the cover letter and interview preparation details into a applications list.
        """
        print(
            Fore.YELLOW + "----- Saving cover letter & interview -----\n" + Style.RESET_ALL
        )
        return {"applications": [
            JobApplication(
                job_description=state["job_description"], 
                cover_letter=state["cover_letter"], 
                interview_preparation=state["interview_prep"]
            )
        ]}