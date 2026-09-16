# Use official Python image
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy your requirements file first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install -r requirements.txt

# Copy the rest of your backend code
COPY . .

# The default command when the container starts
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]