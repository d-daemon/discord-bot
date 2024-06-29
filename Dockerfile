# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file into the container at /app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY ./cogs cogs
COPY ./data data
COPY ./utils utils
COPY bot.py Dockerfile LICENSE ./

# Run bot.py when the container launches
CMD ["python", "bot.py"]
