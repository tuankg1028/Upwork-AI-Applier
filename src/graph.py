from langgraph.graph import END, StateGraph
from colorama import Fore, Style
from .nodes import MainGraphNodes, CreateJobApplicationNodes
from .state import ApplicationState, ApplicationStateInput, MainGraphState, MainGraphStateInput

# Path to the cover letter template file
COVER_LETTERS_FILE = "./files/cover_letter.md"

class UpworkAutomation:
    def __init__(self, profile, num_jobs=10, batch_size=5):
        """
        Initialize the Upwork automation tool with user profile, job count, and batch size.

        Args:
            profile: User profile information for job applications.
            num_jobs (int): Number of jobs to process.
            batch_size (int): Batch size for parallel job processing.
        """
        self.profile = profile
        self.number_of_jobs = num_jobs
        self.batch_size = batch_size
        self.graph = self.build_graph()

    def build_graph(self):
        """
        Build the state graph for automating Upwork job applications.

        Returns:
            Compiled main graph for the automation process.
        """
        # Create job application subgraph
        create_job_application_nodes = CreateJobApplicationNodes(self.profile)
        generate_application_subgraph = StateGraph(ApplicationState, input=ApplicationStateInput)

        # Define subgraph nodes for generating job applications
        generate_application_subgraph.add_node(create_job_application_nodes.gather_relevant_infos_from_profile)
        generate_application_subgraph.add_node(create_job_application_nodes.generate_cover_letter)
        generate_application_subgraph.add_node(create_job_application_nodes.generate_interview_preparation)
        generate_application_subgraph.add_node( create_job_application_nodes.finalize_job_application)

        # Set entry point and define transitions for the subgraph
        generate_application_subgraph.set_entry_point("gather_relevant_infos_from_profile")
        generate_application_subgraph.add_edge("gather_relevant_infos_from_profile", "generate_cover_letter")
        generate_application_subgraph.add_edge("gather_relevant_infos_from_profile", "generate_interview_preparation")
        generate_application_subgraph.add_edge("generate_cover_letter", "finalize_job_application")
        generate_application_subgraph.add_edge("generate_interview_preparation", "finalize_job_application")
        generate_application_subgraph.add_edge("finalize_job_application", END)

        # Create main automation graph
        main_automation_nodes = MainGraphNodes(self.profile, self.number_of_jobs, self.batch_size)
        main_graph = StateGraph(MainGraphState, input=MainGraphStateInput)

        # Define main graph nodes for the workflow
        main_graph.add_node(main_automation_nodes.scrape_upwork_jobs)
        main_graph.add_node(main_automation_nodes.score_scraped_jobs)
        main_graph.add_node(main_automation_nodes.check_for_job_matches)
        main_graph.add_node(main_automation_nodes.generate_jobs_applications)
        main_graph.add_node("create_job_application_content", generate_application_subgraph.compile())
        main_graph.add_node(main_automation_nodes.save_generated_jobs_application)

        # Define transitions for the main graph
        main_graph.set_entry_point("scrape_upwork_jobs")
        main_graph.add_conditional_edges("scrape_upwork_jobs", main_automation_nodes.initiate_jobs_scoring, ["score_scraped_jobs"])
        main_graph.add_edge("score_scraped_jobs", "check_for_job_matches")
        main_graph.add_conditional_edges(
            "check_for_job_matches",
            main_automation_nodes.need_to_process_matches,
            {"Process jobs": "generate_jobs_applications", "No matches": END}
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
            {"Process jobs": "generate_jobs_applications", "No matches": END}
        )
        
        # Compile and return the main graph
        return main_graph.compile()

    async def run(self, job_title):
        """
        Execute the Upwork automation workflow.

        Args:
            job_title (str): Title of the job to process.

        Returns:
            Final state of the automation process.
        """
        print(Fore.BLUE + "----- Running Upwork Jobs Automation -----\n" + Style.RESET_ALL)
        config = {"recursion_limit": 1000}
        state = await self.graph.ainvoke({"job_title": job_title}, config)
        return state
