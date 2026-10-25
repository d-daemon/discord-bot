# Discord Bot

![Production Build Status](https://github.com/d-daemon/discord-bot/actions/workflows/docker-image.yml/badge.svg?branch=main)
![Python Version](https://img.shields.io/badge/Python-3.9_|_3.10_|_3.11_|_3.12_|_3.13_|_3.14_|_3.15-blue.svg)
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
    # Docker image tag (latest or dev)
    IMAGE_TAG=latest

    # PostgreSQL configuration
    POSTGRES_USER=
    POSTGRES_PASSWORD=
    POSTGRES_DB=

    # Discord bot configuration
    DISCORD_BOT_TOKEN=
    INSTAGRAM_COOKIES=
    ```

### GitHub Actions and Docker Hub

1. Set Up GitHub Secrets:

   Go to your repository on GitHub and add the following secrets:

     - `DOCKER_USERNAME`: Your Docker Hub username.
     - `DOCKER_PASSWORD`: Your Docker Hub password or access token.

   Only the Docker Hub secrets are needed by the workflow. The bot and PostgreSQL settings belong in the `.env` file on the host that runs Compose.

2. The Workflow:

   [`.github/workflows/docker-image.yml`](.github/workflows/docker-image.yml) builds and publishes the image on every push to `main` or `dev` (and can be run manually from the Actions tab). It does not deploy the bot.

   | Branch | Published tags |
   | ------ | -------------- |
   | `main` | `latest`, `sha-<short-sha>` |
   | `dev`  | `dev`, `sha-<short-sha>` |

### Docker Compose

1. Review [`compose.yml`](compose.yml). It runs PostgreSQL and the bot, using the image `hhxcusco/discord-bot:${IMAGE_TAG:-latest}`.

2. Choose the image tag with `IMAGE_TAG` in your `.env` file (see `.env.example`), or inline:

     ```bash
     # Production image (default)
     docker compose up -d

     # Dev image
     IMAGE_TAG=dev docker compose up -d
     ```

3. To build the image locally instead of pulling it:

      ```bash
      docker build -t hhxcusco/discord-bot:local .
      IMAGE_TAG=local docker compose up -d
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

This project is licensed under the MIT License. See the [LICENSE](https://github.com/d-daemon/discord-bot/blob/main/LICENSE) file for more information.

This README covers setting up and running the bot locally and in Docker, and publishing its image with GitHub Actions and Docker Hub.
