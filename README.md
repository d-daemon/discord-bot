# Discord Bot

![Production Build Status](https://github.com/d-daemon/discord-bot/actions/workflows/docker-image.yml/badge.svg?branch=main)
![Python Version](https://img.shields.io/badge/Python-3.10_|_3.11_|_3.12_|_3.13_|_3.14_|_3.15-blue.svg)
![License](https://img.shields.io/github/license/d-daemon/discord-bot)
![Docker Pulls](https://img.shields.io/docker/pulls/hhxcusco/discord-bot)
![Docker Image Size](https://img.shields.io/docker/image-size/hhxcusco/discord-bot/latest)
![GitHub Issues](https://img.shields.io/github/issues/d-daemon/discord-bot)
![GitHub Forks](https://img.shields.io/github/forks/d-daemon/discord-bot)
![Last Commit](https://img.shields.io/github/last-commit/d-daemon/discord-bot)

A `discord.py` bot with moderation, utility, and media commands. Run it with Docker Compose and PostgreSQL.

## Features

- Welcome and goodbye messages, configured by text-channel name.
- Moderation commands, including kick and ban, with Discord permission checks.
- Fun and information commands, including dice rolls, jokes, and user details.
- Video and Instagram photo downloads.
- Translation and currency conversion commands.
- Optional cogs for greetings and bot personalization. These are not loaded by default.

## Using the bot

### Requirements

- Docker
- A Discord bot token

In the [Discord Developer Portal](https://discord.com/developers/applications), enable the **Server Members Intent** and **Message Content Intent** for the bot. Invite it to your server with the `bot` and `applications.commands` scopes and the permissions needed for the commands you plan to use.

For example, welcome messages need permission to view and send messages in their configured channels, and moderation commands need the corresponding moderation permissions.

### Run with Docker Compose

1. Clone the repository and prepare its environment file:

   ```bash
   git clone https://github.com/d-daemon/discord-bot.git
   cd discord-bot
   cp .env.example .env
   ```

2. Create three directories for the bot and postgres database:

   ```bash
   mkdir data config db
   ```

3. Edit `.env` and set `DISCORD_BOT_TOKEN`, `POSTGRES_DB`, `POSTGRES_USER`, a strong `POSTGRES_PASSWORD`, and `PUID`/`PGID`.

4. Start the bot and its PostgreSQL database:

   ```bash
   docker compose up -d
   ```

   Compose uses the published `hhxcusco/discord-bot:latest` image. To follow startup or diagnose problems:

   ```bash
   docker compose logs -f discord-bot
   ```

5. To update to the latest published image:

   ```bash
   docker compose pull
   docker compose up -d
   ```

### Configure the bot

Edit `config/config.json`to set the command prefix and the names of the text channels used for welcome and goodbye messages. For example:

```json
{
  "prefix": "!",
  "welcome_channel": "general",
  "goodbye_channel": "general"
}
```

The config directory is mounted into the container. Restart the bot after changing the file:

```bash
docker compose restart discord-bot
```

Optional environment settings:

- `INSTAGRAM_COOKIES`: Instagram session cookies may be needed to download some posts.
- `DEEPL_API_KEY` and `MYMEMORY_API_KEY`: optional translation service credentials. Translation uses Google's no-key endpoint first, then DeepL when configured, then MyMemory. MyMemory can also be used without a key, subject to its lower anonymous quota. Public endpoints may rate-limit requests.

## Contributing

This section is for people contributing to the repository.

### Development setup

The project supports Python `>=3.10, <3.16`. It uses [uv](https://docs.astral.sh/uv/) and the committed `uv.lock` to manage development dependencies.

1. Clone the repository and install the development dependencies:

   ```bash
   git clone https://github.com/d-daemon/discord-bot.git
   cd discord-bot
   uv sync --group dev
   ```

2. Create three directories for the bot and postgres database:

   ```bash
   mkdir data config db
   ```

3. To run the bot locally, ensure your `.env` file is created and run:

   ```bash
   docker compose -f compose.local.yml up --build -d
   ```

4. Run the tests and linter before submitting changes:

   ```bash
   uv run python -m pytest
   uv run ruff check .
   ```

### Docker image workflow

![Production Build Status](https://github.com/d-daemon/discord-bot/actions/workflows/docker-image.yml/badge.svg?branch=main)

The [Docker image workflow](.github/workflows/docker-image.yml) builds and publishes the image to Docker Hub on pushes to `main` or `dev`, and can also be run manually from the Actions tab. It publishes these tags:

| Branch | Published tags              |
| ------ | --------------------------- |
| `main` | `latest`, `sha-<short-sha>` |
| `dev`  | `dev`, `sha-<short-sha>`    |

This workflow publishes an image; it does not deploy or run the bot.

Repository maintainers need to configure the `DOCKER_USERNAME` and `DOCKER_PASSWORD` GitHub Actions secrets for Docker Hub publishing. These are contributor/maintainer settings, not bot runtime settings.

### Submit a change

1. Fork the repository and create a branch for your change.
2. Make your changes and run the tests and linter above.
3. Commit and push your branch.
4. Open a pull request.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
