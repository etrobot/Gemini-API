#!/usr/bin/env python3
"""
Local development server runner for Gemini WebAPI
"""

import os
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Gemini WebAPI server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📖 API docs available at: http://localhost:8000/docs")
    print("🔍 Health check: http://localhost:8000/health")
    print()
    print("ℹ️  Authentication: Provide __Secure-1PSID and __Secure-1PSIDTS cookies in request headers")
    print()
    
    # Run the server
    uvicorn.run(
        "gemini_webapi.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src"]
    )