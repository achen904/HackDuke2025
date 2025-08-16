// Frontend configuration for Duke Eats
export const config = {
  // Backend API URL - change this for production
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000',
  
  // Production URL
  PRODUCTION_URL: 'https://dukebdeats.colab.duke.edu',
  
  // Environment detection
  IS_PRODUCTION: import.meta.env.PROD || false,
  
  // API endpoints
  ENDPOINTS: {
    GET_MEAL_PLAN: '/api/get_meal_plan',
    CHAT: '/api/chat',
    HEALTH: '/api/health'
  }
};

// Helper function to get full API URL
export const getApiUrl = (endpoint: string): string => {
  return `${config.API_BASE_URL}${endpoint}`;
};
