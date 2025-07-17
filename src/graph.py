from langgraph.graph import END, StateGraph
from colorama import Fore, Style
from typing import Optional, Dict, Any
from .nodes import MainGraphNodes, CreateJobApplicationNodes
from .state import ApplicationState, ApplicationStateInput, MainGraphState, MainGraphStateInput
from .config import get_config, UpworkConfig
from .logger import logger
from .session_manager import workflow_session, workflow_state_manager
from .quality_validator import quality_validator

class UpworkAutomation:
    def __init__(self, profile: str, config: Optional[UpworkConfig] = None, **kwargs):
        """
        Initialize the Upwork automation tool with user profile and configuration.

        Args:
            profile: User profile information for job applications.
            config: Optional configuration object. If None, uses global config.
            **kwargs: Legacy parameters for backward compatibility.
        """
        # Load configuration
        self.config = config or get_config()
        
        # Handle legacy parameters
        if 'num_jobs' in kwargs:
            self.config.max_jobs_per_run = kwargs['num_jobs']
        if 'batch_size' in kwargs:
            self.config.scraping.batch_size = kwargs['batch_size']
        
        self.profile = profile
        self.session_id: Optional[str] = None
        self.graph = self.build_graph()
        
        logger.info(f"Initialized UpworkAutomation with config: jobs={self.config.max_jobs_per_run}, batch_size={self.config.scraping.batch_size}")

    def build_graph(self):
        """
        Build the enhanced state graph for automating Upwork job applications.

        Returns:
            Compiled main graph for the automation process.
        """
        # Create job application subgraph with enhanced validation
        create_job_application_nodes = CreateJobApplicationNodes(self.profile, self.config)
        generate_application_subgraph = StateGraph(ApplicationState, input=ApplicationStateInput)

        # Define enhanced subgraph nodes for generating job applications
        generate_application_subgraph.add_node("gather_relevant_infos_from_profile", create_job_application_nodes.gather_relevant_infos_from_profile)
        generate_application_subgraph.add_node("generate_cover_letter_versions", create_job_application_nodes.generate_cover_letter_versions)
        generate_application_subgraph.add_node("select_best_cover_letter", create_job_application_nodes.select_best_cover_letter)
        generate_application_subgraph.add_node("generate_interview_preparation", create_job_application_nodes.generate_interview_preparation)
        generate_application_subgraph.add_node("validate_application_quality", create_job_application_nodes.validate_application_quality)
        generate_application_subgraph.add_node("finalize_job_application", create_job_application_nodes.finalize_job_application)

        # Set entry point and define transitions for the enhanced subgraph
        generate_application_subgraph.set_entry_point("gather_relevant_infos_from_profile")
        generate_application_subgraph.add_edge("gather_relevant_infos_from_profile", "generate_cover_letter_versions")
        generate_application_subgraph.add_edge("gather_relevant_infos_from_profile", "generate_interview_preparation")
        generate_application_subgraph.add_edge("generate_cover_letter_versions", "select_best_cover_letter")
        generate_application_subgraph.add_edge("select_best_cover_letter", "validate_application_quality")
        generate_application_subgraph.add_edge("generate_interview_preparation", "validate_application_quality")
        generate_application_subgraph.add_edge("validate_application_quality", "finalize_job_application")
        generate_application_subgraph.add_edge("finalize_job_application", END)

        # Create enhanced main automation graph
        main_automation_nodes = MainGraphNodes(
            self.profile, 
            self.config.max_jobs_per_run, 
            self.config.scraping.batch_size,
            self.config
        )
        main_graph = StateGraph(MainGraphState, input=MainGraphStateInput)

        # Define enhanced main graph nodes for the workflow
        main_graph.add_node("initialize_session", main_automation_nodes.initialize_session)
        main_graph.add_node("scrape_upwork_jobs", main_automation_nodes.scrape_upwork_jobs)
        main_graph.add_node("score_scraped_jobs", main_automation_nodes.score_scraped_jobs)
        main_graph.add_node("check_for_job_matches", main_automation_nodes.check_for_job_matches)
        main_graph.add_node("generate_jobs_applications", main_automation_nodes.generate_jobs_applications)
        main_graph.add_node("create_job_application_content", generate_application_subgraph.compile())
        main_graph.add_node("save_generated_jobs_application", main_automation_nodes.save_generated_jobs_application)
        main_graph.add_node("generate_session_report", main_automation_nodes.generate_session_report)

        # Define enhanced transitions for the main graph
        main_graph.set_entry_point("initialize_session")
        main_graph.add_edge("initialize_session", "scrape_upwork_jobs")
        main_graph.add_conditional_edges("scrape_upwork_jobs", main_automation_nodes.initiate_jobs_scoring, ["score_scraped_jobs"])
        main_graph.add_edge("score_scraped_jobs", "check_for_job_matches")
        main_graph.add_conditional_edges(
            "check_for_job_matches",
            main_automation_nodes.need_to_process_matches,
            {"Process jobs": "generate_jobs_applications", "No matches": "generate_session_report"}
        )
        main_graph.add_conditional_edges(
            "generate_jobs_applications",
            main_automation_nodes.initiate_content_generation,
            ["create_job_application_content"],
        )
        main_graph.add_edge("create_job_application_content", "save_generated_jobs_application")
        main_graph.add_conditional_edges(
            "save_generated_jobs_application",
            main_automation_nodes.need_to_process_matches,
            {"Process jobs": "generate_jobs_applications", "No matches": "generate_session_report"}
        )
        main_graph.add_edge("generate_session_report", END)
        
        # Compile and return the enhanced main graph
        return main_graph.compile()

    async def run(self, job_title: str, resume_session: Optional[str] = None, config_overrides: Optional[Dict[str, Any]] = None):
        """
        Execute the enhanced Upwork automation workflow.

        Args:
            job_title (str): Title of the job to process.
            resume_session (str, optional): Session ID to resume from.
            config_overrides (dict, optional): Configuration overrides for this run.

        Returns:
            Final state of the automation process.
        """
        logger.info(f"Starting Upwork automation for job title: {job_title}")
        
        # Use session context manager for better state management
        with workflow_session(job_title, config_overrides) as session_id:
            self.session_id = session_id
            
            # Prepare initial state
            initial_state = {
                "job_title": job_title,
                "resume_session": resume_session,
                "config_overrides": config_overrides or {}
            }
            
            # Configure graph execution
            graph_config = {
                "recursion_limit": 1000,
                "debug": self.config.debug_mode
            }
            
            # Execute the workflow
            try:
                logger.info("Executing workflow graph...")
                state = await self.graph.ainvoke(initial_state, graph_config)
                
                logger.info("Workflow completed successfully")
                return state
                
            except Exception as e:
                logger.error(f"Workflow execution failed: {e}")
                raise
    
    def resume_workflow(self, session_id: str):
        """
        Resume a workflow from a saved session.
        
        Args:
            session_id (str): The session ID to resume from.
            
        Returns:
            The resumed workflow state.
        """
        logger.info(f"Resuming workflow from session: {session_id}")
        
        # Try to resume the session
        if workflow_state_manager.resume_session(session_id):
            self.session_id = session_id
            logger.info(f"Successfully resumed session {session_id}")
            return True
        else:
            logger.error(f"Failed to resume session {session_id}")
            return False
    
    def get_session_status(self) -> Optional[Dict[str, Any]]:
        """
        Get the current session status and progress.
        
        Returns:
            Session status information or None if no active session.
        """
        if not self.session_id:
            return None
            
        from .session_manager import session_manager
        session = session_manager.get_session(self.session_id)
        return dict(session) if session else None
    
    def get_resumable_sessions(self) -> List[Dict[str, Any]]:
        """
        Get list of sessions that can be resumed.
        
        Returns:
            List of resumable session information.
        """
        from .session_manager import session_manager
        return [dict(session) for session in session_manager.get_resumable_sessions()]
