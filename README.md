# Discord Bot

![Production Build Status](https://github.com/d-daemon/discord-bot/actions/workflows/docker-image.yml/badge.svg?branch=master)
![Python Version](https://img.shields.io/badge/Python-3.9_|_3.10_|_3.11-blue.svg)
![License](https://img.shields.io/github/license/d-daemon/discord-bot)
![Docker Pulls](https://img.shields.io/docker/pulls/hhxcusco/discord-bot)
![Docker Image Size](https://img.shields.io/docker/image-size/hhxcusco/discord-bot/latest)
![GitHub Issues](https://img.shields.io/github/issues/d-daemon/discord-bot)
![GitHub Forks](https://img.shields.io/github/forks/d-daemon/discord-bot)
![Last Commit](https://img.shields.io/github/last-commit/d-daemon/discord-bot)


A Discord bot built using `discord.py` for various functionalities such as moderation, fun commands, informational commands, and more. This bot is containerized using Docker and can be easily deployed using Docker and GitHub Actions.

## Features

- **Welcome and Goodbye Messages**: Sends welcome messages when a new member joins and goodbye messages when a member leaves.
- **Bot Personalization**: Customize the bot's status, activity, and profile picture.
- **Moderation Commands**: Includes commands like kick and ban.
- **Fun Commands**: Commands like dice rolling and jokes.
- **Informational Commands**: Commands to fetch user information.
- **Video Download Commands**: Download videos from various platforms including Instagram, YouTube, TikTok, Facebook, and more.
- **Photo Download Command**: Download photos from Instagram.

## Setup Instructions

### Prerequisites

- Python 3.9+
- Docker
- Docker Compose (optional, for easier deployment)
- [GitHub account](https://github.com/)
- [Docker Hub account](https://hub.docker.com/)

### Local Development

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/d-daemon/discord-bot.git
   cd discord-bot
    ```

2. Install Dependencies:

     ```bash
     pip install -r requirements.txt
     ```

3. Set Environment Variables:

     Create a `.env` file in the root directory with the following content:

     ```dotenv
     DISCORD_BOT_TOKEN={DISCORD_BOT_TOKEN}
     DATABASE_URL=postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@postgresql:5432/{POSTGRES_DB}
     POSTGRES_USER={POSTGRES_USER}
     POSTGRES_PASSWORD={POSTGRES_PASSWORD}
     POSTGRES_DB={POSTGRES_DB}
      ```        

### GitHub Actions and Docker Hub

1. Set Up GitHub Secrets:

   Go to your repository on GitHub and add the following secrets:
   
     - `DOCKER_USERNAME`: Your Docker Hub username.
     - `DOCKER_PASSWORD`: Your Docker Hub password.
     - `DISCORD_BOT_TOKEN`: Your Discord bot token.
     - `DATABASE_URL`: Your PostgreSQL database url.
     - `POSTGRES_USER`: Your PostgreSQL username.
     - `POSTGRES_PASS`: Your PostgreSQL password.
     - `POSTGRES_DB`: Your PostgreSQL database name.

2. Create a GitHub Actions Workflow:

   Create a file named `docker-image.yml` in the `.github/workflows` directory with the following content. 
   
     ```yaml
   name: Docker Image CI/CD
   
   on:
     push:
       branches:
         - main
         - dev
   
   jobs:
     build:
       runs-on: ubuntu-latest
   
       steps:
         - name: Checkout code
           uses: actions/checkout@v4
   
         - name: Set up Docker Buildx
           uses: docker/setup-buildx-action@v3
   
         - name: Log in to Docker Hub
           uses: docker/login-action@v3
           with:
             username: ${{ secrets.DOCKER_USERNAME }}
             password: ${{ secrets.DOCKER_PASSWORD }}
   
         - name: Build and push Docker image
           uses: docker/build-push-action@v5
           with:
             context: .
             push: true
             tags: |
               hhxcusco/discord-bot:${{ github.ref == 'refs/heads/main' && 'latest' || 'dev' }}
             cache-from: type=registry,ref=hhxcusco/discord-bot:${{ github.ref == 'refs/heads/main' && 'latest' || 'dev' }}
             cache-to: type=inline
   
         - name: Install Docker Compose
           run: |
             sudo apt-get update
             sudo apt-get install -y docker-compose
   
         - name: Deploy
           env:
             DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
             DATABASE_URL: ${{ secrets.DATABASE_URL }}
             DEV_POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
             DEV_POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
             DEV_POSTGRES_DB: ${{ secrets.POSTGRES_DB }}
           run: docker-compose -f docker-compose.yml up -d
     ```
   
### Docker Compose
   
1. Create a `docker-compose.yml` File:
   
     ```yaml
   version: '3.8'
   services:
     postgresql:
       image: postgres:latest
       container_name: postgresql-snow
       environment:
         POSTGRES_DB: ${POSTGRES_DB}
         POSTGRES_USER: ${POSTGRES_USER}
         POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
         POSTGRES_HOST_AUTH_METHOD: trust
         PGDATA: /var/lib/postgresql/data/pgdata
       command: 
         - "postgres"
         - "-c"
         - "listen_addresses=*"
         - "-c"
         - "max_connections=100"
         - "-c"
         - "shared_buffers=256MB"
       volumes:
         - ./postgresql/data:/var/lib/postgresql/data/pgdata
         - ./postgresql/init:/docker-entrypoint-initdb.d
       ports:
         - "5433:5432"
       restart: unless-stopped
       healthcheck:
         test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
         interval: 5s
         timeout: 5s
         retries: 5
       networks:
         - discord-bot-net
   
     discord-bot:
       build:
         context: .
       image: discord-bot:dev
       container_name: discord-bot-snow
       ports:
         - "26218:5000"
       environment:
         DISCORD_BOT_TOKEN: ${DISCORD_BOT_TOKEN}
         DATABASE_URL: ${DATABASE_URL}
       volumes:
         - ./config:/app/config
         - ./data:/app/data
       restart: unless-stopped
       networks:
         - discord-bot-net
   
   networks:
     discord-bot-net:
       driver: bridge
     ```

2. Build the Docker Image:

      ```bash
      docker build -t discord-bot .
      ```

3. Deploy with Docker Compose:

     ```bash
     docker-compose up -d --build
     ```

4. Update the config.json in the `config` folder:

      ```json
      {
       "prefix": "!",
       "welcome_channel": "town-square",
       "goodbye_channel": "town-square"
      }
      ```

5. Restart the container for the changes to take effect. 

## Contributing
1. Fork the repository.
2. Create a new branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -m 'Add Your Feature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Create a new Pull Request.

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/d-daemon/discord-bot/blob/master/LICENSE) file for more information.

This README provides a comprehensive guide to setting up and running your Discord bot, both locally and in Docker, as well as deploying it using GitHub Actions and Docker Hub. If you need any adjustments or additional information, feel free to ask!
