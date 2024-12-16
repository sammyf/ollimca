#!/bin/bash

# Default values
DEFAULT_VISION_MODEL="moondream:latest"
DEFAULT_EMBED_MODEL="nomic-embed-text:latest"
DEFAULT_TEMPERATURE=0.5

# Prompt user for vision model (default is 'llama3.2-vision:11b')
read -p "Enter the vision model (default: $DEFAULT_VISION_MODEL): " VISION_MODEL
VISION_MODEL=${VISION_MODEL:-$DEFAULT_VISION_MODEL}

# Prompt user for embedding model (default is 'nomic-embed-text:latest')
read -p "Enter the embedding model (default: $DEFAULT_EMBED_MODEL): " EMBED_MODEL
EMBED_MODEL=${EMBED_MODEL:-$DEFAULT_EMBED_MODEL}

# Prompt user for temperature (default is 0.5)
read -p "Enter the temperature (default: $DEFAULT_TEMPERATURE): " TEMPERATURE
TEMPERATURE=${TEMPERATURE:-$DEFAULT_TEMPERATURE}

# File to update
FILE_TO_UPDATE="ollimca.py"

# Replace placeholders with user input using sed
sed -i "s/VISION_MODEL/$VISION_MODEL/g" "$FILE_TO_UPDATE"
sed -i "s/EMBED_MODEL/$EMBED_MODEL/g" "$FILE_TO_UPDATE"
sed -i "s/TEMPERATURE/$TEMPERATURE/g" "$FILE_TO_UPDATE"

echo "Updated $FILE_TO_UPDATE with the provided values."
echo "You will need to edit the file ollimca.py +(lines 28-30) manually if you want to change those values."
