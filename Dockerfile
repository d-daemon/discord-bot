FROM python:3.9-slim

# Set work directory
WORKDIR /app

# Copy application files
COPY ./cogs /app/cogs
COPY ./data /app/data
COPY ./utils /app/utils
COPY bot.py /app/
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "bot.py"]
