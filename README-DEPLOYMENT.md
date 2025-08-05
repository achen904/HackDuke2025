# Duke Eats - Docker Deployment Guide

This guide explains how to deploy the Duke Eats application using Docker on a VM or any server.

## Prerequisites

- Docker installed on your VM
- Docker Compose installed
- API keys for Gemini and OpenAI

## Quick Start

### 1. Set up Environment Variables

Create a `.env` file in the project root:

```bash
# Duke Eats Environment Variables
GEMINI_API_KEY=your_actual_gemini_api_key_here
OPENAI_API_KEY=your_actual_openai_api_key_here
```

### 2. Deploy the Application

Use the automated deployment script:

```bash
# Basic deployment (port 3000)
./deploy.sh deploy

# Production deployment with nginx (port 80)
./deploy.sh deploy:prod
```

## Manual Deployment

If you prefer to deploy manually:

### 1. Build and Run

```bash
# Build the Docker image
docker-compose build

# Start the application
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 2. Production Deployment

```bash
# Deploy with nginx reverse proxy
docker-compose --profile production up -d
```

## Deployment Script Commands

The `deploy.sh` script provides several useful commands:

```bash
./deploy.sh deploy        # Deploy application (default)
./deploy.sh deploy:prod   # Deploy with production profile
./deploy.sh logs          # Show application logs
./deploy.sh stop          # Stop the application
./deploy.sh status        # Show application status
./deploy.sh cleanup       # Clean up all Docker resources
./deploy.sh help          # Show help message
```

## Architecture Overview

The Docker setup includes:

### Dockerfile
- **Multi-stage build**: Builds React frontend and Python backend
- **Security**: Runs as non-root user
- **Optimization**: Uses Alpine Linux for smaller image size
- **Health checks**: Monitors application health

### Docker Compose
- **Main service**: Duke Eats application
- **Optional nginx**: Reverse proxy for production
- **Environment variables**: Secure API key management
- **Volume mounting**: Database persistence
- **Networking**: Isolated network for services

### Nginx Configuration
- **Reverse proxy**: Routes traffic to Flask backend
- **Rate limiting**: Protects against abuse
- **Security headers**: Enhanced security
- **Gzip compression**: Better performance
- **SSL support**: HTTPS configuration (commented)

## Production Considerations

### 1. SSL/HTTPS Setup

To enable HTTPS, uncomment the SSL section in `nginx.conf` and:

1. Obtain SSL certificates
2. Place them in `./ssl/` directory
3. Update the server_name in nginx.conf
4. Deploy with production profile

### 2. Environment Variables

For production, consider using Docker secrets or a secure environment variable management system.

### 3. Database Persistence

The SQLite database is mounted as a volume. For production, consider:
- Using PostgreSQL or MySQL
- Setting up database backups
- Implementing proper database migrations

### 4. Monitoring and Logging

Consider adding:
- Application monitoring (Prometheus/Grafana)
- Centralized logging (ELK stack)
- Health check endpoints
- Performance monitoring

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Check what's using the port
   sudo netstat -tulpn | grep :3000
   
   # Stop conflicting services
   sudo systemctl stop conflicting-service
   ```

2. **API key errors**
   - Ensure `.env` file exists and contains valid API keys
   - Check that keys are not placeholder values

3. **Build failures**
   ```bash
   # Clean up and rebuild
   docker-compose down
   docker system prune -f
   docker-compose build --no-cache
   ```

4. **Application not starting**
   ```bash
   # Check logs
   docker-compose logs duke-eats
   
   # Check health endpoint
   curl http://localhost:3000/api/health
   ```

### Debugging Commands

```bash
# Enter the container
docker-compose exec duke-eats bash

# Check container resources
docker stats

# View detailed container info
docker inspect duke-eats-app

# Check network connectivity
docker network ls
docker network inspect hackduke2025_duke-eats-network
```

## Scaling

### Horizontal Scaling

To scale the application:

```bash
# Scale to multiple instances
docker-compose up -d --scale duke-eats=3
```

### Load Balancing

The nginx configuration can be extended to support multiple backend instances.

## Backup and Recovery

### Database Backup

```bash
# Backup the database
docker-compose exec duke-eats cp duke_nutrition.db duke_nutrition.db.backup

# Copy from container to host
docker cp duke-eats-app:/app/duke_nutrition.db.backup ./backups/
```

### Full Application Backup

```bash
# Create a backup of the entire application
tar -czf duke-eats-backup-$(date +%Y%m%d).tar.gz \
    --exclude=node_modules \
    --exclude=venv \
    --exclude=.git \
    .
```

## Security Best Practices

1. **Keep images updated**: Regularly update base images
2. **Use secrets**: Store sensitive data in Docker secrets
3. **Network isolation**: Use custom networks
4. **Non-root user**: Application runs as non-root
5. **Security headers**: Nginx provides security headers
6. **Rate limiting**: Prevents abuse
7. **Regular updates**: Keep dependencies updated

## Performance Optimization

1. **Multi-stage builds**: Reduces final image size
2. **Alpine Linux**: Smaller base image
3. **Gzip compression**: Reduces bandwidth usage
4. **Static asset caching**: Better performance
5. **Health checks**: Ensures application availability

## Support

For deployment issues:
1. Check the logs: `./deploy.sh logs`
2. Verify environment variables
3. Ensure Docker and Docker Compose are installed
4. Check system resources (CPU, memory, disk space) 