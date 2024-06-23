# Discord Bot

![Build Status](https://github.com/d-daemon/discord-bot/actions/workflows/docker-image.yml/badge.svg)
![Python Version](https://img.shields.io/badge/Python-3.9-blue.svg)

A Discord bot built using `discord.py` for various functionalities such as moderation, fun commands, informational commands, and more. This bot is containerized using Docker and can be easily deployed using Docker and GitHub Actions.

## Features

- **Welcome and Goodbye Messages**: Sends welcome messages when a new member joins and goodbye messages when a member leaves.
- **Moderation Commands**: Includes commands like kick and ban.
- **Role Management**: Add or remove roles from users.
- **Fun Commands**: Commands like dice rolling and jokes.
- **Informational Commands**: Commands to fetch user information.

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

3. Create Configuration Files:

Create a `config.json` file in the data directory:

  ```json
  {
    "prefix": "!"
  }
  ```

4. Set Environment Variables:

  Create a `.env` file in the root directory with the following content:

  ```dotenv
  DISCORD_BOT_TOKEN=your_bot_token_here
  ```

5. Run the Bot:

  ```bash
  python bot.py
  ```

### Docker Setup

1. Build the Docker Image:

  ```bash
  docker build -t discord-bot .
  ```

2. Run the Docker Container:

  ```bash
  docker run -d --name discord-bot -e DISCORD_BOT_TOKEN=your_bot_token_here -p 26218:5000 discord-bot
  ```

### Docker Compose

1. Create a `docker-compose.yml` File:

  ```yaml
  version: '3'
  
  services:
    discord-bot:
      image: hhxcusco/discord-bot:latest
      container_name: discord-bot
      ports:
        - 26218:5000
      restart: always
      environment:
        - DISCORD_BOT_TOKEN=your_bot_token_here
  ```

2. Deploy with Docker Compose:

```bash
docker-compose up -d
```

### GitHub Actions and Docker Hub

1. Set Up GitHub Secrets:

Go to your repository on GitHub and add the following secrets:

  - `DOCKER_USERNAME`: Your Docker Hub username.
  - `DOCKER_PASSWORD`: Your Docker Hub password.
  - `DISCORD_BOT_TOKEN`: Your Discord bot token.

2. Create a GitHub Actions Workflow:

Create a file named `docker-image.yml` in the `.github/workflows` directory with the following content. 

  ```yaml
  name: Docker

  on:
    push:
      branches:
        - master

  jobs:
    build:
      runs-on: ubuntu-latest

      steps:
        - name: Checkout code
          uses: actions/checkout@v2

        - name: Set up Docker Buildx
          uses: docker/setup-buildx-action@v1

        - name: Log in to Docker Hub
          uses: docker/login-action@v1
          with:
            username: ${{ secrets.DOCKER_USERNAME }}
            password: ${{ secrets.DOCKER_PASSWORD }}

        - name: Build and push Docker image
          uses: docker/build-push-action@v2
          with:
            push: true
            tags: hhxcusco/discord-bot:latest

        - name: Deploy
          env:
            DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
          run: docker run -d --name discord-bot -e DISCORD_BOT_TOKEN=${{ secrets.DISCORD_BOT_TOKEN }} -p 26218:5000 hhxcusco/discord-bot:latest
  ```

## Contributing
1. Fork the repository.
2. Create a new branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -m 'Add Your Feature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Create a new Pull Request.

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/d-daemon/discord-bot/blob/master/LICENSE) file for more information.

This README provides a comprehensive guide to setting up and running your Discord bot, both locally and in Docker, as well as deploying it using GitHub Actions and Docker Hub. If you need any adjustments or additional information, feel free to ask!
