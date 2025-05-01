import re
import asyncio
import hashlib
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm_asyncio
from playwright.async_api import async_playwright
from src.utils import ainvoke_llm, get_playwright_browser_context, convert_html_to_markdown
from src.database import job_exists
from src.structured_outputs import JobInformation
from src.prompts import SCRAPER_PROMPT


class UpworkJobScraper:
    """
    Scrapes Upwork job data based on a search query.
    """

    def __init__(self, batch_size=5):
        """
        Initializes the UpworkJobScraper with a specified batch size for parallel scraping.

        Args:
            batch_size (int): The number of jobs to scrape in parallel. Defaults to 5.
        """
        self.batch_size = batch_size

    async def scrape_upwork_data(self, search_query="AI agent Developer", num_jobs=10):
        """
        Scrapes Upwork job data based on the search query in batches of 5 jobs at a time.
        """
        url = f"https://www.upwork.com/nx/search/jobs?q={search_query}&sort=recency&page=1&per_page={num_jobs}"

        async with async_playwright() as playwright:
            browser = await playwright.firefox.launch(headless=True)
            browser_context = await get_playwright_browser_context(browser)
            page = await browser_context.new_page()

            # Scrape the main search page
            await page.goto(url)
            html_content = await page.content()
            jobs_links_list = self.extract_jobs_urls(html_content)
            await page.close()  # Ensure the page is closed

            semaphore = asyncio.Semaphore(self.batch_size)  # Limit concurrency to batch size tasks
            jobs_data = []

            async def scrape_job_with_semaphore(link):
                """Wrapper to scrape a job with a semaphore."""
                async with semaphore:
                    return await self.scrape_job_details(browser, link)

            # Scrape job pages in batches
            for i in tqdm_asyncio(range(0, len(jobs_links_list), self.batch_size), desc="Scraping job pages in batches"):
                batch_links = jobs_links_list[i:i+5]
                batch_results = await asyncio.gather(
                    *[scrape_job_with_semaphore(link) for link in batch_links]
                )
                jobs_data.extend(batch_results)

            await browser.close()

            # Filter out None results
            jobs_data = [job for job in jobs_data if job]

            # Process and return the job info data
            jobs_data = self.process_job_info_data(jobs_data)
                
            return jobs_data
    
    def extract_job_id_from_url(self, url):
        """
        Extract job ID from a job URL.
        """
        # Extract the part between 'apply/' and '/?referrer'
        match = re.search(r'apply/([^/]+)/?', url)
        if match:
            return match.group(1)
        return None

    def extract_jobs_urls(self, html):
        """
        Extracts job URLs from the HTML content and filters out already collected jobs.
        """
        soup = BeautifulSoup(html, 'html.parser')
        job_links = []
        skipped_count = 0
        
        for h2 in soup.find_all('h2', class_='job-tile-title'):
            a_tag = h2.find('a')
            if a_tag:
                job_link = a_tag['href'].replace('/jobs', 'https://www.upwork.com/freelance-jobs/apply', 1)
                job_id = self.extract_job_id_from_url(job_link)
                
                # Skip if job already exists in database
                if job_id and job_exists(job_id):
                    skipped_count += 1
                    continue
                
                # clean the job url
                job_link = job_link.split('?')[0] if '?' in job_link else job_link 
                job_links.append(job_link)
        
        if skipped_count > 0:
            print(f"Skipped {skipped_count} already collected jobs")
            
        return job_links

    async def scrape_job_details(self, browser, url):
        """
        Scrapes and processes a single job page.
        """
        try:
            browser_context = await get_playwright_browser_context(browser)
            page = await browser_context.new_page()
            # Set a custom timeout for navigation
            await page.goto(url, timeout=60000)  # Set timeout to 60 seconds
            await asyncio.sleep(1)  # Allow the page to fully load
            html_content = await page.content()

            # Parse the HTML to extract the <main> content of the page
            soup = BeautifulSoup(html_content, "html.parser")
            main_content = soup.find("main", id="main")
            job_page_content_markdown = convert_html_to_markdown(main_content)

            information = await ainvoke_llm(
                system_prompt=SCRAPER_PROMPT,
                user_message=f"Scrape all the relevant job details from the content of this page:\n\n{job_page_content_markdown}",
                model="openai/gpt-4o-mini",
                response_format=JobInformation,
            )
            job_info_dict = information.model_dump()

            # Process the job type from enum
            job_info_dict["job_type"] = information.job_type.value

            # Include job link in the output
            job_info_dict["link"] = url
            
            # Extract and add job_id
            job_id = self.extract_job_id_from_url(url)
            
            # hash the job_id
            job_info_dict["job_id"] = hashlib.sha256(job_id.encode()).hexdigest()

            # Ensure field names match the database schema
            # Map client_information fields to the correct database field names
            client_info = job_info_dict.pop("client_information", None)
            if client_info:
                job_info_dict.update({
                    f"client_{key}": value
                    for key, value in client_info.items()
                })

            return job_info_dict
        except Exception as e:
            print(f"Error processing link {url}: {e}")
            return None
        finally:
            await page.close()  # Ensure the page is closed

    def process_job_info_data(self, jobs_data):
        for job in jobs_data:
            if job.get("payment_rate"):
                job["payment_rate"] = re.sub(
                    r"\$?(\d+\.?\d*)\s*\n*-\n*\$?(\d+\.?\d*)", r"$\1-$\2", job["payment_rate"]
                )
        return jobs_data