# Multi-stage Dockerfile for Duke Eats application
FROM node:18-alpine AS frontend-builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install Node.js dependencies (remove --only=production for build stage)
RUN npm ci

# Copy frontend source code
COPY . .

# Build the React application
RUN npm run build

# Python backend stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Health check (install curl first)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the built frontend from the previous stage
COPY --from=frontend-builder /app/dist ./dist

# Copy frontend files for fallback (in case dist doesn't have everything)
COPY index.html .
COPY index.css .
COPY index.js .
COPY index.tsx .

# Copy Python backend files
COPY server.py .
COPY agent.py .
COPY duke_nutrition.db .

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 3000

# Set environment variables
ENV FLASK_APP=server.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Run the application
CMD ["python", "server.py"] 