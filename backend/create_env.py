#!/usr/bin/env python
"""Create .env file with required variables"""
from pathlib import Path

env_content = """DATABASE_URL=postgresql://legal_diff_user:dev123@localhost:5432/legal_diff
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
SECRET_KEY=dev-secret-key-change-in-production
OPENAI_API_KEY=sk-bf8cb200fe8f4b2e99e6f81e2511a083
DEEPSEEK_API_KEY=sk-bf8cb200fe8f4b2e99e6f81e2511a083
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
BACKEND_CORS_ORIGINS=["http://localhost:3000", "http://localhost:3003", "http://localhost:5173"]
"""

env_path = Path(__file__).parent / ".env"

if env_path.exists():
    print(f".env file already exists at: {env_path}")
    print("Checking if it has required variables...")
    
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required = ['DATABASE_URL', 'CELERY_BROKER_URL', 'CELERY_RESULT_BACKEND', 'SECRET_KEY']
    missing = [var for var in required if f"{var}=" not in content]
    
    if missing:
        print(f"Missing variables: {', '.join(missing)}")
        print("Adding missing variables...")
        with open(env_path, 'a', encoding='utf-8') as f:
            f.write("\n# Added by create_env.py\n")
            for line in env_content.split('\n'):
                if line.strip() and any(line.startswith(f"{var}=") for var in missing):
                    f.write(line + "\n")
        print("Missing variables added!")
    else:
        print("All required variables are present.")
else:
    print(f"Creating .env file at: {env_path}")
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    print(".env file created successfully!")

print(f"\n.env file location: {env_path.absolute()}")
print("\nIMPORTANT: Make sure PostgreSQL and Redis are running!")
print("  Run: docker compose -f docker-compose.dev.yml up -d")
