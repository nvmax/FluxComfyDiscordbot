FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    build-essential \
    nginx \
    redis-server \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create Main/DataSets directory
RUN mkdir -p Main/DataSets

# Copy config files first
COPY Main/Datasets/*.json /app/Main/DataSets/

# Copy the rest of the application
COPY . .

# Install Python dependencies
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Set environment variables
ENV COMMAND_PREFIX=/
ENV BOT_SERVER=0.0.0.0
ENV server_address=0.0.0.0

# Expose ports
EXPOSE 8080

# Verify files are present (for debugging)
RUN ls -la /app/Main/DataSets/

# Start the Discord bot
CMD ["python3", "bot.py"]