"""
API Configuration
Set your API keys and other configuration here
"""

class APIConfig:
    # OpenAI Configuration
    # Get your API key from: https://platform.openai.com/api-keys
    OPENAI_API_KEY = "sk-your-actual-api-key-here"  # Replace with your actual key
    
    # OpenAI Model Settings
    OPENAI_MODEL = "gpt-4o-mini"
    OPENAI_TEMPERATURE = 0.1
    OPENAI_MAX_TOKENS = 3000
    
    # AWS S3 Configuration (if needed)
    AWS_ACCESS_KEY_ID = "your-aws-key"
    AWS_SECRET_ACCESS_KEY = "your-aws-secret"
    AWS_REGION = "us-east-1"
    S3_BUCKET = "eob-dev-bucket"
    
    # Database Configuration
    MONGODB_URL = "mongodb://localhost:27017/"
    POSTGRES_URL = "postgresql://user:password@localhost/eob835"
    
    @classmethod
    def is_openai_configured(cls):
        """Check if OpenAI is properly configured"""
        return (cls.OPENAI_API_KEY and 
                cls.OPENAI_API_KEY != "sk-your-actual-api-key-here" and
                len(cls.OPENAI_API_KEY) > 20)
    
    @classmethod
    def get_openai_key(cls):
        """Get OpenAI API key"""
        if cls.is_openai_configured():
            return cls.OPENAI_API_KEY
        return None