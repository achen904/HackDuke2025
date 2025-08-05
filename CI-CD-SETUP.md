# CI/CD Setup Guide for Duke Eats

This guide will help you set up automated deployment of Duke Eats to your VM using GitHub Actions.

## 🚀 Quick Setup Overview

1. **Prepare your VM** - Run setup script
2. **Configure GitHub Secrets** - Add VM credentials
3. **Push to main branch** - Trigger deployment
4. **Monitor deployment** - Check GitHub Actions

## 📋 Prerequisites

- A VM/server with Ubuntu 20.04+ or similar Linux distribution
- SSH access to your VM
- GitHub repository with admin access
- API keys for Gemini and OpenAI

## 🖥️ Step 1: Prepare Your VM

### Option A: Automated Setup (Recommended)

1. **Download and run the setup script on your VM:**
   ```bash
   curl -o vm-setup.sh https://raw.githubusercontent.com/achen904/HackDuke2025/main/vm-setup.sh
   chmod +x vm-setup.sh
   ./vm-setup.sh
   ```

2. **Edit the environment file:**
   ```bash
   cd /opt/duke-eats
   nano .env
   ```
   
   Replace the placeholder values:
   ```bash
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   OPENAI_API_KEY=your_actual_openai_api_key_here
   ```

### Option B: Manual Setup

If you prefer manual setup:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create app directory
sudo mkdir -p /opt/duke-eats
sudo chown $USER:$USER /opt/duke-eats
cd /opt/duke-eats

# Create .env file with your API keys
nano .env
```

## 🔐 Step 2: Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these repository secrets:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `VM_HOST` | Your VM's IP address or domain | `192.168.1.100` or `your-domain.com` |
| `VM_USER` | SSH username for your VM | `ubuntu` or `your-username` |
| `VM_SSH_KEY` | Private SSH key for VM access | Contents of your `~/.ssh/id_rsa` |
| `VM_PORT` | SSH port (optional, defaults to 22) | `22` |
| `VM_APP_PATH` | Path to app on VM (optional) | `/opt/duke-eats` |

### 🔑 Setting up SSH Key

1. **On your local machine, generate an SSH key pair:**
   ```bash
   ssh-keygen -t rsa -b 4096 -C "github-actions@duke-eats"
   ```

2. **Copy the public key to your VM:**
   ```bash
   ssh-copy-id -i ~/.ssh/id_rsa.pub user@your-vm-ip
   ```

3. **Copy the private key content to GitHub secrets:**
   ```bash
   cat ~/.ssh/id_rsa
   ```
   Copy the entire output (including `-----BEGIN` and `-----END` lines) to the `VM_SSH_KEY` secret.

## 🚀 Step 3: Deploy

### Automatic Deployment

1. **Push to main branch:**
   ```bash
   git add .
   git commit -m "Setup CI/CD deployment"
   git push origin main
   ```

2. **Monitor the deployment:**
   - Go to GitHub → Actions tab
   - Watch the "Deploy Duke Eats to VM" workflow
   - Check each step: Test → Build → Deploy

### Manual Deployment

You can also trigger deployment manually:
- Go to GitHub → Actions
- Select "Deploy Duke Eats to VM"
- Click "Run workflow"

## 📊 Step 4: Verify Deployment

### Check Application Status

1. **On your VM:**
   ```bash
   cd /opt/duke-eats
   docker-compose ps
   docker-compose logs -f
   ```

2. **Test the application:**
   ```bash
   curl http://localhost:3000/api/health
   ```

3. **Access from browser:**
   ```
   http://YOUR_VM_IP:3000
   ```

### Monitoring Commands

```bash
# Check application status
sudo systemctl status duke-eats

# View logs
docker-compose logs -f duke-eats

# Check resource usage
docker stats

# Update application
./update-app.sh
```

## 🔧 Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   ```bash
   # Test SSH connection
   ssh -i ~/.ssh/id_rsa user@your-vm-ip
   
   # Check SSH key permissions
   chmod 600 ~/.ssh/id_rsa
   ```

2. **Docker Permission Denied**
   ```bash
   # On VM, add user to docker group
   sudo usermod -aG docker $USER
   # Then logout and login again
   ```

3. **Port Already in Use**
   ```bash
   # Check what's using port 3000
   sudo netstat -tulpn | grep :3000
   
   # Stop conflicting service
   sudo systemctl stop conflicting-service
   ```

4. **Health Check Failing**
   ```bash
   # Check application logs
   docker-compose logs duke-eats
   
   # Test health endpoint directly
   docker-compose exec duke-eats curl http://localhost:3000/api/health
   ```

### Debug GitHub Actions

1. **Check workflow logs in GitHub Actions tab**
2. **Verify secrets are correctly set**
3. **Test SSH connection manually**
4. **Check VM disk space and resources**

## 🔒 Security Considerations

1. **Firewall Setup:**
   ```bash
   # On your VM
   sudo ufw allow ssh
   sudo ufw allow 3000
   sudo ufw allow 80    # If using nginx
   sudo ufw allow 443   # If using HTTPS
   sudo ufw --force enable
   ```

2. **SSH Security:**
   ```bash
   # Disable password authentication (optional)
   sudo nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   sudo systemctl restart ssh
   ```

3. **Docker Security:**
   - Images are automatically scanned by GitHub
   - Application runs as non-root user
   - Network isolation via Docker networks

## 📈 Advanced Features

### Enable HTTPS with Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Update nginx.conf to enable HTTPS
# Then deploy with production profile
docker-compose --profile production up -d
```

### Monitoring Setup

```bash
# Set up basic monitoring
docker run -d \
  --name=cadvisor \
  --restart=unless-stopped \
  -p 8080:8080 \
  -v /:/rootfs:ro \
  -v /var/run:/var/run:ro \
  -v /sys:/sys:ro \
  -v /var/lib/docker/:/var/lib/docker:ro \
  gcr.io/cadvisor/cadvisor:latest
```

## 🎯 Workflow Customization

The GitHub Actions workflow supports:

- **Automatic testing** before deployment
- **Multi-stage builds** for optimization
- **Container registry** for image storage
- **Health checks** after deployment
- **Rollback capabilities** (manual)

### Environment-specific Deployments

To deploy to different environments, create additional workflows:

```yaml
# .github/workflows/deploy-staging.yml
name: Deploy to Staging
on:
  push:
    branches: [ develop ]
# ... similar configuration with different secrets
```

## 📞 Support

If you encounter issues:

1. Check the [GitHub Actions logs](../../actions)
2. Verify all secrets are correctly configured
3. Test SSH access manually
4. Check VM resources and logs
5. Review the troubleshooting section above

## 🔄 Updates and Maintenance

- **Automatic updates**: Push to main branch triggers deployment
- **Manual updates**: Run `./update-app.sh` on VM
- **Database backups**: Implement regular backups of `duke_nutrition.db`
- **Security updates**: Keep VM and Docker updated

Your Duke Eats application is now ready for continuous deployment! 🎉
