# Duke Eats Deployment Guide

## Local Development

1. Start the backend server:
   ```bash
   python3 server.py
   ```
   The server will run on `http://localhost:3000`

2. Start the frontend:
   ```bash
   npm run dev
   ```
   The frontend will run on `http://localhost:5173`

## Production Deployment

### Backend Configuration

1. Update the `.env` file with valid credentials:
   ```bash
   OPENAI_API_KEY=your_valid_api_key_here
   OPENAI_API_BASE=https://litellm.oit.duke.edu
   ```

2. Set environment variables for production:
   ```bash
   export FLASK_ENV=production
   export BACKEND_HOST=0.0.0.0
   export BACKEND_PORT=3000
   ```

3. Start the production server:
   ```bash
   python3 server.py
   ```

### Frontend Configuration

1. For production deployment, update `production-config.js`:
   ```javascript
   export const productionConfig = {
     API_BASE_URL: 'https://dukebdeats.colab.duke.edu',
     FRONTEND_URL: 'https://dukebdeats.colab.duke.edu',
     ENV: 'production'
   };
   ```

2. Build for production:
   ```bash
   npm run build
   ```

3. Deploy the `dist` folder to your production server.

## API Key Issues

If you encounter authentication errors:
1. Check that your Duke LiteLLM API key is valid
2. Ensure the API key has the correct permissions
3. Verify the `OPENAI_API_BASE` URL is correct
4. Contact Duke OIT if the API key has expired

## Troubleshooting

- **Backend not connecting**: Check if the server is running on the correct port
- **API authentication errors**: Verify your API key and base URL
- **CORS issues**: Ensure the backend allows requests from your frontend domain
