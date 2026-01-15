# -----------------------------------------------------------------------------
# Project: Routers | MikroTik
# Author: fsdevcom2000
# GitHub: https://github.com/fsdevcom2000/router-monitor
# -----------------------------------------------------------------------------

# --- Not for production (for dev only) ---
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        reload=False,
    )

# Start in production
# from app.main import app

# uvicorn run:app \
#   --host 0.0.0.0 \
#   --port ${PORT:-5000} \
#   --workers 2 \
#   --log-level info \
#   --access-log
