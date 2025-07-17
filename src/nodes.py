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
from .config import get_config

class MainGraphNodes:
    def __init__(self, profile, num_jobs=10, batch_size=3, config=None):
        self.profile = profile
        self.number_of_jobs = num_jobs
        self.batch_size = batch_size
        self.config = config or get_config()
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
        Score a batch of jobs using enhanced scoring with AI-powered analysis.

        @param state: The current state with a batch of jobs.
        @return: Updated state with scored jobs.
        """
        print(Fore.YELLOW + "----- Scoring a batch of jobs with enhanced analysis -----\n" + Style.RESET_ALL)
        
        try:
            # Try enhanced scoring first
            from .enhanced_scoring import score_jobs_enhanced
            
            scoring_results = await score_jobs_enhanced(state["jobs_batch"], self.profile)
            
            # Convert to expected format
            scores = []
            for result in scoring_results:
                scores.append({
                    "score": result.overall_score / 10,  # Convert to 0-10 scale
                    "confidence": result.confidence_score / 100,
                    "reasoning": result.explanation
                })
            
            return {"scores": scores}
            
        except Exception as e:
            print(f"Enhanced scoring failed, falling back to original method: {e}")
            
            # Fallback to original scoring
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
        
        # Use configured minimum score threshold
        min_score = self.config.scoring.minimum_score
        jobs_matched = [job for job in all_jobs if job["score"] >= min_score]
        
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
    def __init__(self, profile, config=None):
        self.profile = profile
        self.config = config or get_config()
        
        # Import here to avoid circular imports
        from .client_intelligence import analyze_client_success
        from .enhanced_scoring import create_enhanced_scorer
        from .dynamic_personalization import create_personalization_engine
        from .multi_version_generator import generate_content_versions
        from .quality_validator import quality_validator
        from .visual_elements import generate_visual_package, integrate_visuals_into_proposal
        from .advanced_quality_assurance import comprehensive_quality_assessment
        from .smart_followup import create_followup_strategy
        
        self.analyze_client_success = analyze_client_success
        self.enhanced_scorer = create_enhanced_scorer(profile)
        self.personalization_engine = create_personalization_engine()
        self.generate_content_versions = generate_content_versions
        self.quality_validator = quality_validator
        self.comprehensive_quality_assessment = comprehensive_quality_assessment
        self.generate_visual_package = generate_visual_package
        self.integrate_visuals_into_proposal = integrate_visuals_into_proposal
        self.create_followup_strategy = create_followup_strategy

    async def gather_relevant_infos_from_profile(self, state: ApplicationState):
        """
        Gather relevant information from the freelancer profile and perform enhanced analysis.

        @param state: Current application state.
        @return: Updated state with relevant information.
        """
        print(Fore.YELLOW + "----- Gathering Relevant Information from Profile -----\n" + Style.RESET_ALL)
        
        # Extract job data from state
        job_data = {
            'job_id': state.get('job_id', 'unknown'),
            'title': state.get('job_title', ''),
            'description': state.get('job_description', ''),
            'payment_rate': state.get('payment_rate', ''),
            'experience_level': state.get('experience_level', ''),
            'client_total_spent': state.get('client_total_spent', '$0'),
            'client_total_hires': state.get('client_total_hires', 0),
            'client_location': state.get('client_location', 'Unknown'),
            'client_joined_date': state.get('client_joined_date', 'Unknown'),
            'client_company_profile': state.get('client_company_profile', '')
        }
        
        # Perform enhanced analysis
        try:
            # Client intelligence analysis
            client_analysis = await self.analyze_client_success(job_data, {'description': job_data['description']})
            
            # Enhanced job scoring
            scoring_result = await self.enhanced_scorer.score_job(job_data)
            
            # Dynamic personalization
            personalization_context = await self.personalization_engine.create_personalization_context(
                job_data, client_analysis, scoring_result
            )
            
            # Generate visual elements package
            visual_package = await self.generate_visual_package(
                job_data, client_analysis, scoring_result, personalization_context, self.profile
            )
            
            # Original profile analysis
            profile_analysis_prompt = PROFILE_ANALYZER_PROMPT.format(profile=self.profile)
            profile_information = await ainvoke_llm(
                system_prompt=profile_analysis_prompt,
                user_message=state["job_description"],
                model="openai/gpt-4o-mini"
            )
            
            return {
                "relevant_infos": profile_information,
                "client_analysis": client_analysis,
                "scoring_result": scoring_result,
                "personalization_context": personalization_context,
                "visual_package": visual_package
            }
            
        except Exception as e:
            print(f"Error in enhanced analysis: {e}")
            # Fallback to original analysis
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

    async def generate_cover_letter_versions(self, state: ApplicationState):
        """
        Generate multiple versions of cover letters using AI-powered multi-version generation.
        
        @param state: Current application state with enhanced analysis data.
        @return: Updated state with multiple cover letter versions.
        """
        print(Fore.YELLOW + "----- Generating Multiple Cover Letter Versions -----\n" + Style.RESET_ALL)
        
        try:
            # Check if we have enhanced analysis data
            if all(key in state for key in ['client_analysis', 'scoring_result', 'personalization_context']):
                # Extract job data from state
                job_data = {
                    'job_id': state.get('job_id', 'unknown'),
                    'title': state.get('job_title', ''),
                    'description': state.get('job_description', ''),
                    'payment_rate': state.get('payment_rate', ''),
                    'experience_level': state.get('experience_level', ''),
                    'client_total_spent': state.get('client_total_spent', '$0'),
                    'client_total_hires': state.get('client_total_hires', 0),
                    'client_location': state.get('client_location', 'Unknown'),
                    'client_joined_date': state.get('client_joined_date', 'Unknown'),
                    'client_company_profile': state.get('client_company_profile', '')
                }
                
                # Generate multiple versions
                version_results = await self.generate_content_versions(
                    job_data,
                    state['client_analysis'],
                    state['scoring_result'],
                    state['personalization_context'],
                    self.profile
                )
                
                return {
                    "cover_letter_versions": version_results,
                    "primary_cover_letter": version_results.primary_version.content,
                    "alternative_versions": [v.content for v in version_results.alternative_versions]
                }
            else:
                # Fallback to single version generation
                return await self.generate_cover_letter(state)
                
        except Exception as e:
            print(f"Error in multi-version generation: {e}")
            # Fallback to original method
            return await self.generate_cover_letter(state)

    async def select_best_cover_letter(self, state: ApplicationState):
        """
        Select the best cover letter version based on performance predictions.
        
        @param state: Current application state with cover letter versions.
        @return: Updated state with selected best cover letter.
        """
        print(Fore.YELLOW + "----- Selecting Best Cover Letter Version -----\n" + Style.RESET_ALL)
        
        try:
            if 'cover_letter_versions' in state:
                version_results = state['cover_letter_versions']
                
                # Use the recommended version
                best_version_id = version_results.recommended_version
                best_version = next(
                    (v for v in [version_results.primary_version] + version_results.alternative_versions 
                     if v.variation_id == best_version_id), 
                    version_results.primary_version
                )
                
                print(f"Selected {best_version.version.value} version with {best_version.strategy.value} strategy")
                
                return {
                    "cover_letter": best_version.content,
                    "selected_version": best_version,
                    "version_metadata": {
                        'version_type': best_version.version.value,
                        'strategy': best_version.strategy.value,
                        'tone': best_version.tone.value,
                        'personalization_score': best_version.personalization_score
                    }
                }
            else:
                # Fallback if no versions available
                return {"cover_letter": state.get('cover_letter', state.get('primary_cover_letter', ''))}
                
        except Exception as e:
            print(f"Error in version selection: {e}")
            return {"cover_letter": state.get('cover_letter', state.get('primary_cover_letter', ''))}

    async def validate_application_quality(self, state: ApplicationState):
        """
        Validate the quality of the generated application using advanced AI-powered quality assessment.
        
        @param state: Current application state with cover letter and interview prep.
        @return: Updated state with comprehensive quality validation results.
        """
        print(Fore.YELLOW + "----- Advanced Quality Validation -----\n" + Style.RESET_ALL)
        
        try:
            # Get the cover letter and job information
            cover_letter = state.get('cover_letter', '')
            job_description = state.get('job_description', '')
            
            # Extract company info if available
            company_info = None
            if 'personalization_context' in state:
                company_info = state['personalization_context'].company_research.company_name
            
            if cover_letter and job_description:
                # Perform comprehensive quality assessment
                quality_assessment = await self.comprehensive_quality_assessment(
                    cover_letter, job_description, self.profile, company_info
                )
                
                # Check if quality meets standards
                quality_passed = quality_assessment.overall_score >= 70
                
                if quality_passed:
                    print(f"✓ Advanced quality validation passed with score: {quality_assessment.overall_score:.1f}/100")
                    print(f"  Quality Level: {quality_assessment.overall_level.value.upper()}")
                    print(f"  Confidence: {quality_assessment.confidence:.1f}%")
                else:
                    print(f"⚠ Quality validation concerns - score: {quality_assessment.overall_score:.1f}/100")
                    print(f"  Quality Level: {quality_assessment.overall_level.value.upper()}")
                    
                    if quality_assessment.recommendations:
                        print("Top Recommendations:")
                        for rec in quality_assessment.recommendations[:3]:
                            print(f"  - {rec}")
                
                # Display key insights
                if quality_assessment.strengths:
                    print(f"Strengths: {', '.join(quality_assessment.strengths[:2])}")
                
                if quality_assessment.improvement_areas:
                    print(f"Areas for improvement: {', '.join(quality_assessment.improvement_areas[:2])}")
                
                return {
                    "quality_validation": quality_assessment,
                    "quality_passed": quality_passed,
                    "quality_score": quality_assessment.overall_score,
                    "quality_level": quality_assessment.overall_level.value,
                    "quality_confidence": quality_assessment.confidence,
                    "quality_recommendations": quality_assessment.recommendations,
                    "quality_strengths": quality_assessment.strengths,
                    "quality_issues": quality_assessment.improvement_areas
                }
            else:
                # Basic validation if no content available
                basic_quality = len(cover_letter) > 100
                return {
                    "quality_passed": basic_quality,
                    "quality_score": 75 if basic_quality else 40,
                    "quality_level": "good" if basic_quality else "poor"
                }
                
        except Exception as e:
            print(f"Error in advanced quality validation: {e}")
            # Fallback to basic validation
            basic_quality = len(state.get('cover_letter', '')) > 100
            return {
                "quality_passed": basic_quality,
                "quality_score": 70 if basic_quality else 50,
                "quality_level": "fair"
            }

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
        Also integrates visual elements if available.
        """
        print(
            Fore.YELLOW + "----- Finalizing Application with Visual Elements -----\n" + Style.RESET_ALL
        )
        
        # Get the base cover letter
        cover_letter = state.get("cover_letter", "")
        
        # Integrate visual elements if available
        if "visual_package" in state and state["visual_package"].elements:
            try:
                enhanced_cover_letter = self.integrate_visuals_into_proposal(
                    cover_letter, state["visual_package"]
                )
                
                visual_count = len(state["visual_package"].elements)
                print(f"✓ Integrated {visual_count} visual elements into proposal")
                
                # Update cover letter with visual enhancements
                cover_letter = enhanced_cover_letter
                
            except Exception as e:
                print(f"Warning: Could not integrate visual elements: {e}")
                # Continue with original cover letter
        
        # Create application with enhanced content
        application = JobApplication(
            job_description=state["job_description"], 
            cover_letter=cover_letter, 
            interview_preparation=state.get("interview_prep", "")
        )
        
        # Add metadata if available
        if "version_metadata" in state:
            application.metadata = state["version_metadata"]
        
        if "quality_score" in state:
            application.quality_score = state["quality_score"]
        
        # Set visual elements count
        if "visual_package" in state and state["visual_package"].elements:
            application.visual_elements_count = len(state["visual_package"].elements)
        
        # Create follow-up strategy if we have all required data
        followup_strategy = None
        if all(key in state for key in ['client_analysis', 'scoring_result']):
            try:
                # Extract job data from state
                job_data = {
                    'job_id': state.get('job_id', 'unknown'),
                    'title': state.get('job_title', ''),
                    'description': state.get('job_description', ''),
                    'payment_rate': state.get('payment_rate', ''),
                    'experience_level': state.get('experience_level', ''),
                }
                
                # Application data for follow-up analysis
                application_data = {
                    'quality_score': state.get('quality_score', 70),
                    'quality_level': state.get('quality_level', 'good'),
                    'visual_elements_count': state.get('visual_elements_count', 0),
                    'version_metadata': state.get('version_metadata', {})
                }
                
                # Create follow-up strategy
                followup_strategy = await self.create_followup_strategy(
                    job_data, state['client_analysis'], application_data
                )
                
                print(f"✓ Created follow-up strategy with {followup_strategy.total_actions} actions")
                print(f"  Expected success rate: {followup_strategy.estimated_success_rate:.1f}%")
                
            except Exception as e:
                print(f"Warning: Could not create follow-up strategy: {e}")
        
        return {
            "applications": [application],
            "followup_strategy": followup_strategy
        }