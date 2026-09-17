import uvicorn
from app.config import settings

import os

if __name__ == "__main__":
    is_prod = os.getenv("RENDER") is not None or os.getenv("ENVIRONMENT") == "production"
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=not is_prod,
        reload_dirs=["app"] if not is_prod else None
    )
