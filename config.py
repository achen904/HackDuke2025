import os

# Backend configuration
BACKEND_HOST = os.getenv('BACKEND_HOST', '0.0.0.0')
BACKEND_PORT = int(os.getenv('BACKEND_PORT', '3000'))

# OpenAI configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'sk-ieX6eGDeQL6EMUpGzROevA')
OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://litellm.oit.duke.edu')

# Frontend configuration
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')
PRODUCTION_URL = os.getenv('PRODUCTION_URL', 'https://dukebdeats.colab.duke.edu')

# Environment detection
IS_PRODUCTION = os.getenv('NODE_ENV') == 'production' or os.getenv('FLASK_ENV') == 'production'
