from pathlib import Path

import uvicorn


if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent
    uvicorn.run(
        "app.main:app",
        app_dir=str(backend_dir),
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
