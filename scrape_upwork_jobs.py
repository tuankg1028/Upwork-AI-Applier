import asyncio
from src.scraper import UpworkJobScraper
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

if __name__ == "__main__":
    search_query = "AI agent developer"
    number_of_jobs = 10
    
    scraper = UpworkJobScraper()
    result = asyncio.run(scraper.scrape_upwork_data(search_query, number_of_jobs))
    print(f"Result: {result}")
    
    scraper.save_jobs_to_csv(result, "upwork_jobs_data.csv")
