#!/bin/sh

# Ensure the /app/config directory exists
mkdir -p /app/config

# Check if the config.json does not exist
if [ ! -f /app/config/config.json ]; then
    echo "Creating config.json file..."
    # Default configuration contents
    cat << EOF > /app/config/config.json
{
    "prefix": "!",
    "welcome_channel": "general",
    "goodbye_channel": "general"
}
EOF
fi

# Execute the main command (CMD in Dockerfile)
exec "$@"
