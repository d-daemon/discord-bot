# Use an official Python runtime as a parent image
FROM python:3.9-slim
LABEL image="https://hub.docker.com/r/hhxcusco/discord-bot"
LABEL source="https://github.com/d-daemon/discord-bot"

RUN apt-get install -y ffmpeg git curl
COPY requirements.txt ./
RUN pip install -U pip

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create a working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY ./cogs cogs
COPY ./data data
COPY ./utils utils
COPY ./config config
COPY bot.py LICENSE ./

# Expose port 5000 to the outside world
EXPOSE 5000

# Define the volume mount points
VOLUME ["/app/config", "/app/data"]

# Copy entrypoint script and make it executable
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Define the entrypoint and default command
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "bot.py"]
