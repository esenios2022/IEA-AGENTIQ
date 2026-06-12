from fastapi import FastAPI

app = FastAPI(title="IEA-AGENTIQ")


@app.get("/health")
def health_check():
    return {"status": "ok"}
