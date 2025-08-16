// Production configuration for Duke Eats
// Update this file when deploying to production

export const productionConfig = {
  // Backend API URL for production
  API_BASE_URL: 'https://dukebdeats.colab.duke.edu',
  
  // Frontend URL for production
  FRONTEND_URL: 'https://dukebdeats.colab.duke.edu',
  
  // Environment
  ENV: 'production'
};

// Local development configuration
export const localConfig = {
  // Backend API URL for local development
  API_BASE_URL: 'http://localhost:3000',
  
  // Frontend URL for local development
  FRONTEND_URL: 'http://localhost:5173',
  
  // Environment
  ENV: 'development'
};

// Export the appropriate config based on environment
export const config = process.env.NODE_ENV === 'production' ? productionConfig : localConfig;
