from fastapi import FastAPI

app = FastAPI(
    title="Quota Sentinel",
    description="Learning project exploring multi-tenant rate limiting and fair resource allocation.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "quota-sentinel"}


@app.get("/api/v1/data")
def get_sample_data():
    return {
        "message": "Resource payload successfully retrieved.",
        "status": "success",
    }
