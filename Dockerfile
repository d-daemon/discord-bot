# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Metadata
LABEL image="https://hub.docker.com/r/hhxcusco/discord-bot"
LABEL source="https://github.com/d-daemon/discord-bot"

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create a working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Copy and prepare the entrypoint script from the docker directory
COPY docker/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Define the entrypoint to initialize the container environment
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Set the default command to run when starting the container
CMD ["python", "bot.py"]
