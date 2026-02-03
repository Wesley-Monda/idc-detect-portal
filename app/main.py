from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from .database import engine, Base
from .routers import auth, patient, pathologist

# Create DB Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="IDC Detect Portal", debug=True)

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include Routers
app.include_router(auth.router)
app.include_router(patient.router)
app.include_router(pathologist.router)

@app.get("/")
async def root():
    return RedirectResponse(url="/login")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
