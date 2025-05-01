# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libx11-xcb1 libxcomposite1 libxrandr2 libxdamage1 libxkbcommon0 libgbm1 libasound2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && playwright install firefox

# Expose any necessary ports (if applicable)
EXPOSE 8000

# Set environment variables (optional, can also be passed via docker-compose)
ENV OPENAI_API_KEY=""
ENV GOOGLE_API_KEY=""
ENV GROQ_API_KEY=""
ENV LANGCHAIN_TRACING_V2="true"
ENV LANGCHAIN_API_KEY=""
ENV LANGCHAIN_PROJECT="Upwork Automation"

# Command to run the application
CMD ["python", "main.py"]