# Use the official Python 3.12.4 slim image
FROM python:3.12-slim-bullseye


# Set environment variables for the Python script

#this is where is the root folder where are the pyhton modules where the funtions will be transformed in API endpoints
ENV PYHON_MODULES_DIRECTORY="archives"

#this what folders to ignore that are sub folders inside of the PYHON_MODULES_FOLDER, should be  a list, whre each item is separetad by comma ','
ENV IGNORE=="venv,__pycache__"

#this argument will be passed to any funtion that has 'apify_modules_args' as input argument
ENV MODULES_ARGS=""

# Set environment variable for port
ENV EXPOSE_PORT=9000

ENV DEBUG="false"

# Set working directory
WORKDIR /

# Copy the current directory (excluding folders/files in .dockerignore)
COPY . .

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt


# Command to run your Python application
CMD ["python", "apify.py"]