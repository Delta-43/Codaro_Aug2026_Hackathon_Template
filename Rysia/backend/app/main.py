"""Entry point for the Track B booking API.

Run it with: uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs to see (and try) every endpoint —
FastAPI builds that page automatically from the code below.
"""

from fastapi import FastAPI

app = FastAPI(title="Codaro Track B API")


@app.get("/health")
def health():
    """A tiny endpoint with no real logic — just proves the server is alive.

    Deployment tools and teammates ping this first when something seems
    broken: if /health doesn't respond, the problem is "the server isn't
    running," not "the booking logic has a bug" — and that's a much
    faster thing to rule out.
    """
    return {"status": "ok"}
