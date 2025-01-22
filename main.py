import asyncio
from dotenv import load_dotenv
from src.utils import read_text_file
from src.graph import UpworkAutomation

# Load environment variables from a .env file
load_dotenv()

if __name__ == "__main__":
    # Job title to look for
    job_title = "AI agent Developer"

    # load the freelancer profile
    profile = read_text_file("./files/profile.md")

    # run automation
    automation = UpworkAutomation(profile)
    asyncio.run(automation.run(job_title=job_title))
    
    # Visualize automation graph as a PNG image
    # output_path = "./output_graph.png"  # Specify the desired output path
    # with open(output_path, "wb") as file:
    #     file.write(automation.graph.get_graph().draw_mermaid_png())
    # print(f"Graph saved as PNG at {output_path}")
