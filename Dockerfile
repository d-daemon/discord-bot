# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create a working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Define the volume mount points
VOLUME ["/app/config", "/app/data"]

# Copy entrypoint script and make it executable
COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Define the entrypoint and default command
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "bot.py"]
