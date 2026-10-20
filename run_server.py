"""Server launcher for CareSaathi AI Web Application.
Runs FastAPI on http://127.0.0.1:8080
"""
import uvicorn
from caresaathi.config import WEB_PORT, WEB_HOST
from caresaathi.db import init_db

if __name__ == "__main__":
    init_db()
    print(f"Starting CareSaathi AI Web Application on http://{WEB_HOST}:{WEB_PORT}")
    uvicorn.run("web.app:app", host=WEB_HOST, port=WEB_PORT, reload=False)
