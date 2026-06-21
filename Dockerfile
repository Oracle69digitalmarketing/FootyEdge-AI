# Stage 1: Build the React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Final Python Runtime Image
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for build packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy python specifications and install packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files and compiled static assets
COPY . .
COPY --from=frontend-builder /app/dist ./dist

# Expose Render's standard web routing port
EXPOSE 10000

# Fire up Uvicorn on port 10000 to serve the FastAPI app
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "10000"]
