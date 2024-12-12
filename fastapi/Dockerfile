# Use an official Python runtime as a base image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy only the essential files for installing dependencies first
COPY requirements.txt .

# Install Tesseract
RUN apt-get update && apt-get install tesseract-ocr ffmpeg libsm6 libxext6 poppler-utils -y

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port FastAPI will run on
EXPOSE 8000

# Command to run the FastAPI application
CMD ["fastapi", "run", "main.py"]
