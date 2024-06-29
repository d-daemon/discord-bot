FROM python:3.9

# Set work directory
WORKDIR /app

COPY requirements.txt requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Run the bot
CMD ["python", "bot.py"]
