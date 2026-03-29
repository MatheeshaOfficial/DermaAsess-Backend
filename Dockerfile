FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Set the working directory
WORKDIR /app

# Install system dependencies (specifically libgl1 for OpenCV)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pip dependencies independently to cache them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port from env variable
EXPOSE ${PORT}

# Run the FastAPI server
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
