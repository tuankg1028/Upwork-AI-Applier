import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
from src.utils import read_text_file
from src.graph import UpworkAutomation
from src.config import get_config, config_manager
from src.logger import logger
from src.session_manager import session_manager

# Load environment variables from a .env file
load_dotenv()

async def main():
    """Main application entry point"""
    try:
        # Load configuration
        config = get_config()
        
        # Apply environment overrides
        config_manager.apply_environment_overrides()
        
        # Validate configuration
        if not config_manager.validate_config():
            logger.error("Configuration validation failed")
            sys.exit(1)
        
        # Load the freelancer profile
        profile = read_text_file(config.profile_path)
        
        # Initialize automation with configuration
        automation = UpworkAutomation(profile, config)
        
        # Check for resumable sessions
        resumable_sessions = automation.get_resumable_sessions()
        if resumable_sessions:
            logger.info(f"Found {len(resumable_sessions)} resumable sessions")
            for session in resumable_sessions:
                logger.info(f"  - Session {session['session_id']}: {session['job_title']} ({session['status']})")
        
        # Run automation
        if config.dry_run:
            logger.info("Running in DRY RUN mode - no actual applications will be generated")
        
        logger.info(f"Starting automation for job title: {config.job_title}")
        final_state = await automation.run(job_title=config.job_title)
        
        # Display results
        session_info = final_state.get('session_info', {})
        logger.info("=== AUTOMATION RESULTS ===")
        logger.info(f"Jobs scraped: {session_info.get('total_jobs_scraped', 0)}")
        logger.info(f"Jobs scored: {session_info.get('total_jobs_scored', 0)}")
        logger.info(f"Matches found: {session_info.get('total_matches_found', 0)}")
        logger.info(f"Applications generated: {session_info.get('total_applications_generated', 0)}")
        logger.info(f"Applications saved: {session_info.get('total_applications_saved', 0)}")
        
        # Show errors if any
        errors = session_info.get('errors', [])
        if errors:
            logger.warning(f"Encountered {len(errors)} errors during processing")
            for error in errors:
                logger.error(f"  - {error}")
        
        # Display session statistics
        stats = session_manager.get_session_statistics()
        logger.info(f"Session statistics: {stats}")
        
    except KeyboardInterrupt:
        logger.info("Automation interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Automation failed: {e}")
        sys.exit(1)

def visualize_graph():
    """Generate and save workflow visualization"""
    try:
        config = get_config()
        profile = read_text_file(config.profile_path)
        automation = UpworkAutomation(profile, config)
        
        output_path = "./automation_graph.png"
        with open(output_path, "wb") as file:
            file.write(automation.graph.get_graph(xray=True).draw_mermaid_png())
        
        logger.info(f"Workflow graph saved as PNG at {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to generate workflow visualization: {e}")

if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--visualize":
            visualize_graph()
        elif sys.argv[1] == "--config":
            # Display current configuration
            config = get_config()
            print("Current configuration:")
            print(f"  Job title: {config.job_title}")
            print(f"  Max jobs per run: {config.max_jobs_per_run}")
            print(f"  Minimum score: {config.scoring.minimum_score}")
            print(f"  Batch size: {config.scraping.batch_size}")
            print(f"  Debug mode: {config.debug_mode}")
            print(f"  Dry run: {config.dry_run}")
        elif sys.argv[1] == "--sessions":
            # Display session information
            stats = session_manager.get_session_statistics()
            print(f"Session statistics: {stats}")
            
            resumable = session_manager.get_resumable_sessions()
            if resumable:
                print(f"Resumable sessions:")
                for session in resumable:
                    print(f"  - {session['session_id']}: {session['job_title']} ({session['status']})")
        else:
            print("Usage: python main.py [--visualize|--config|--sessions]")
    else:
        # Run the main automation
        asyncio.run(main())
