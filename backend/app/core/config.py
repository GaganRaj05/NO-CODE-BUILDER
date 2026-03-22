import os
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MONGODB_URL = os.getenv('MONGODB_URL')
MONGODB_NAME = os.getenv('MONGODB_NAME')
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
REDIS_URL = os.getenv("REDIS_URL")
FRONTEND_URL = os.getenv('FRONTEND_URL')