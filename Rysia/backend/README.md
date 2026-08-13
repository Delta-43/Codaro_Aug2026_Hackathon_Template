# Backend — quick start

```
python3 -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** in a browser — FastAPI auto-generates an interactive page listing every endpoint, straight from the code. That page is the fastest way to try an endpoint by hand without writing any request code yourself.

`--reload` means the server restarts itself automatically whenever you save a change to a file — useful while building, turn it off in production (see `DECISIONS.md`, not written yet — will note this when we get to deployment/security).
