# Use the official Python 3.12.4 slim image
FROM python:3.12-slim-bullseye

# Set working directory
WORKDIR /

# Copy the current directory (excluding folders/files in .dockerignore)
COPY . .

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt

# Command to run your Python application
CMD ["python", "apify.py"]