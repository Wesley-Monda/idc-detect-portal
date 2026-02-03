from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from .database import engine, Base
from .routers import auth, patient, pathologist

# Create DB Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="IDC Detect Portal", debug=True)

@app.on_event("startup")
async def startup_event():
    # Diagnostics for DB persistence on Vercel
    from . import database, models
    db = next(database.get_db())
    try:
        user_count = db.query(models.User).count()
        print(f"STARTUP: Connected to DB. Active users: {user_count}")
        # Note: In Vercel, /tmp is ephemeral and shared within a lambda instance but not across instances.
    except Exception as e:
        print(f"STARTUP: DB connection test FAILED: {e}")
    finally:
        db.close()

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
