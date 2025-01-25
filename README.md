# UpworkScribe AI: Automated Jobs Application on Upwork

**UpworkScribe AI is not just a tool; it's your partner in navigating the competitive world of freelancing, helping you secure more projects and grow your freelance career. 🚀**

## The Challenge of Modern Freelancing

The freelance marketplace has undergone a dramatic transformation in the digital age. While platforms like Upwork have opened up a world of opportunities, they have also intensified competition. Freelancers often find themselves spending countless hours searching for suitable projects, tailoring proposals, and crafting unique cover letters. This process can be not only time-consuming but also mentally exhausting, leading to missed opportunities and proposal fatigue.

## How UpworkScribe AI Helps

UpworkScribe AI simplifies the freelancing process by acting as your personal assistant. It offers:

* **Automatic Job Scanning and Qualification:** Saves freelancers time by identifying and qualifying the most relevant job opportunities.
* **Personalized Cover Letter:** automate the Creation of tailored cover letters for each project, increasing the chances of standing out to clients.
* **Interview Preparation Support:** Generates materials to help freelancers prepare for client meetings and secure jobs with confidence.
* **24/7 Availability:** can be setup to work around the clock, ensuring no opportunities are missed, even when you're offline.
* **Cost-Effective:** Offers powerful features at a low cost, making it accessible to freelancers at all levels.
* **Support For Multiple LLM Providers:** Can integrate with various large language models, offering flexibility and adaptability to meet different user needs.

## Features

### Jobs Scraping and Classification

- **Job Monitoring**: The system scans Upwork for new project listings of the freelancer provided job titles, ensuring freelancer stay up-to-date.
- **Intelligent Job Scoring**: Each job receives a score based on various criteria such: match with freelancer experience & skills, budget, duration, client history and past projects on the platform,etc. Only jobs scoring 7/10 or higher proceed for further analysis.

### AI Cover Letter and Interview Script Generation

- **Dynamic Cover Letter Creation**: AI agents crafts custom cover letters based on each job description and.
- **Personalized Content**: Tailors cover letters to reflect the user’s unique writing style, skills, and relevant experiences.
- **Interview Script and Questions**: Prepares a list of potential interview questions and a script for the freelancer, covering job-specific topics to improve interview readiness.
- **Keyword Optimization**: Incorporates job-related keywords to enhance proposal relevance and client interest.

---

## How It Works

1. **User Input**: The process starts with the user entering a job title.
2. **Job Scraping**: The system scrapes Upwork for job listings that match the user-provided search queries, gathering relevant opportunities in real-time.
3. **Job Scoring and Filtering**: Each job is scored by an AI agent, and only jobs with a score of 7/10 or higher are presented to the freelancer, filtering out lower-quality matches.
5. **Cover Letter and Interview Preparation**: For strong job matches, the system generates:
   - A personalized cover letter emphasizing the user’s qualifications and alignment with the job.
   - A custom interview preparation script including potential questions to prepare the user for discussions with potential clients.
6. **Review and Submission**: The generated cover letter, interview script, and questions are saved for user review, allowing for final adjustments before submission to prospective clients.

### System Flowchart

This is the detailed flow of the system:

[![](https://mermaid.ink/img/pako:eNqdlMGO2jAQhl_FMlJPoNJyKETtSiEBxGqL2rJ7Sjg49oRYBDuyHegKePc6TlKye1olUiJP8n_zz4xiXzCVDLCH94oUGXoOY4Hs9Ri9aFBoLYrSaPQoE_TMTQ47NBo9ID_aUqsG9FKcpTpUn_Wu5nwnmFuBVIBqGesK6ue8kl1r0Xf07fOX8RWF623g_wmjkGtKFENP8jyqFFzsuwm66MOPhg0uQQb0gFKpXLE_iaEZ6FvXM3DgLyUpaNeStp7RCgQoYsBhflHknBLDpUCBFAaE2XXhjWwzX9FiE0b2ftNW6Lpf3JMG8mSn-ATGgNp1Ncu7Zm191InDuRoXLwz6hH6XoKsi3g5t4chVtCUnQC3uhvuu2GUtrIOVC4JY1KE2r7ltFqU8z70BTdOhNkoewBtMJpNmPTpzZjLva_F3SGUulTcYj8dd3G_wdHbHp9PpR_F5gydJL_egdU-SPnjYuqe98EXrns764Mv_o-uFrxp81s-92WNNEsZYrwlseiXAQ3wEdSSc2dPmUiWMscngCDH27JIRdYhxLG5WR0ojt6-CYs-oEoZYyXKfYS8lubZRWTD744ec2CPr2Ly9_QPS1oVz?type=png)](https://mermaid.live/edit#pako:eNqdlMGO2jAQhl_FMlJPoNJyKETtSiEBxGqL2rJ7Sjg49oRYBDuyHegKePc6TlKye1olUiJP8n_zz4xiXzCVDLCH94oUGXoOY4Hs9Ri9aFBoLYrSaPQoE_TMTQ47NBo9ID_aUqsG9FKcpTpUn_Wu5nwnmFuBVIBqGesK6ue8kl1r0Xf07fOX8RWF623g_wmjkGtKFENP8jyqFFzsuwm66MOPhg0uQQb0gFKpXLE_iaEZ6FvXM3DgLyUpaNeStp7RCgQoYsBhflHknBLDpUCBFAaE2XXhjWwzX9FiE0b2ftNW6Lpf3JMG8mSn-ATGgNp1Ncu7Zm191InDuRoXLwz6hH6XoKsi3g5t4chVtCUnQC3uhvuu2GUtrIOVC4JY1KE2r7ltFqU8z70BTdOhNkoewBtMJpNmPTpzZjLva_F3SGUulTcYj8dd3G_wdHbHp9PpR_F5gydJL_egdU-SPnjYuqe98EXrns764Mv_o-uFrxp81s-92WNNEsZYrwlseiXAQ3wEdSSc2dPmUiWMscngCDH27JIRdYhxLG5WR0ojt6-CYs-oEoZYyXKfYS8lubZRWTD744ec2CPr2Ly9_QPS1oVz)

---

## Tech Stack

-   **LangGraph & LangChain**: Frameworks used for building AI agents and interacting with LLMs (GPT-4o, Llama 3, Gemini).
-   **LangSmith**: For monitoring the different LLM calls and AI agents' interactions.
-   **Playwright**: For scraping and crawling websites.

---

## How to Run

### Setup

1. **Clone the repository:**

   ```sh
   git clone https://github.com/kaymen99/Upwork-AI-jobs-applier.git
   cd Upwork-AI-jobs-applier
   ```

2. **Set up environment variables:**

   Create a `.env` file in the root directory of the project and add your API keys, see `.env.example` to know all the parameters you will need.

### Run Locally

#### Prerequisites

- Python 3.9+
- Necessary Python libraries (listed in `requirements.txt`)
- API keys for LLM models you want to use (OpenAI, Claude, Gemini, Groq,...)

#### Running the Application

1. **Create and activate a virtual environment:**

   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. **Install the required packages:**

   ```sh
   pip install -r requirements.txt
   ```

3. **Start the workflow:**

   ```sh
   python main.py
   ```

   The application will start scraping job listings, classifying them, generating cover letters, and saving the results. By default, all the generated cover letters will be saved in the `data/cover_letter.txt` file alongside a csv file including all the jobs details.

4. **Test the Upwork jobs scraping tool** by running:

   ```sh
   python scrape_upwork_jobs.py
   ```

---

### Run in Docker

#### Prerequisites

- Docker installed on your machine.
- API keys for LLM models you want to use (OpenAI, Claude, Gemini, Groq,...)

#### Running the Application

1. **Build and run the Docker container:**

   ```sh
   docker build -t upwork-auto-jobs-applier-using-ai .
   docker run -e OPENAI_API_KEY=YOUR_API_KEY_HERE -v ./data:/usr/src/app/data upwork-auto-jobs-applier-using-ai
   ```

   The application will start scraping job listings, classifying them, generating cover letters, and saving the results. By default, all the generated cover letters will be saved in the `data/cover_letters.txt` file.

2. **Test the Upwork jobs scraping tool** in Docker by running:

   ```sh
   docker run -e OPENAI_API_KEY=YOUR_API_KEY_HERE -v ./data:/usr/src/app/data upwork-auto-jobs-applier-using-ai python scrape_upwork_jobs.py
   ```

---

### Customization

- To use this automation for your own profile, just add your profile into `files/profile.md` and remove the example profile.

- You can customize the behavior of each AI agent by modifying the corresponding agent prompt in the `prompts` script.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any changes.

## Contact

If you have any questions or suggestions, feel free to contact me at `aymenMir1001@gmail.com`.
