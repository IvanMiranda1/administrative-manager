from fastapi import FastAPI

app = FastAPI(title="Sistema de responsabilidades administrativas")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
