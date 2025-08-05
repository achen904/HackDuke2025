# Duke Eats - AI-Powered Nutrition Assistant

Duke Eats is an intelligent nutrition assistant that helps Duke University students make informed dining choices using AI-powered meal planning and nutritional analysis.

## 🚀 Quick Start

### Local Development

**Prerequisites:** Node.js 18+, Python 3.11+

1. **Install dependencies:**
   ```bash
   npm install
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   Create a `.env.local` file:
   ```bash
   GEMINI_API_KEY=your_gemini_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. **Run the application:**
   ```bash
   # Development mode
   npm run dev
   
   # Or run the full stack
   python server.py
   ```

### 🐳 Docker Deployment

For production deployment with Docker:

```bash
# Quick deployment
./deploy.sh deploy

# Production with nginx
./deploy.sh deploy:prod
```

See [README-DEPLOYMENT.md](README-DEPLOYMENT.md) for detailed Docker deployment instructions.

### 🔄 CI/CD Deployment to VM

For automated deployment to your VM using GitHub Actions:

1. **Set up your VM:** Run the automated setup script
2. **Configure GitHub secrets:** Add VM credentials  
3. **Push to main:** Triggers automatic deployment

See [CI-CD-SETUP.md](CI-CD-SETUP.md) for complete CI/CD setup instructions.
