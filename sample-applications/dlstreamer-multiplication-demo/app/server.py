import asyncio
import logging
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from http import HTTPStatus
from urllib.parse import unquote
from .metrics import SystemMonitor
from .stream import Stream

logger = logging.getLogger(__name__)

app = FastAPI(title="Deep Learning Streamer", root_path="/v1/dlstreamer")
monitor = SystemMonitor()
stream = Stream()


app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=os.getenv("CORS_ALLOW_METHODS", "*").split(","),
    allow_headers=os.getenv("CORS_ALLOW_HEADERS", "*").split(","),
)


@app.get("/health", tags=["Health API"], summary="Check API health status")
async def health():
    """
    Check the health status of the service.

    Returns:
        dict: A dictionary containing the status and message of the service health.
    """
    return {"status": "Success", "message": "Service is up and running."}


@app.get("/metrics", tags=["metrics"], summary="Get system metrics")
async def get_system_metrics(ram_type: str = "percent"):
    try:
        return StreamingResponse(monitor.return_all(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Error getting system metrics. {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting system metrics: {str(e)}",
        )


@app.get("/pipeline/status", tags=["Pipelines"], summary="Get pipeline status")
async def get_pipeline_status():
    try:
        pipeline_status = await asyncio.to_thread(stream.view_pipeline)
        return JSONResponse(content={"status": "Success", "metadata": pipeline_status})
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Error getting pipeline status: {str(e)}",
        )


@app.post("/pipeline/add", tags=["Pipelines"], summary="Add a new pipeline")
async def add_pipeline(stream_path, model_path, target_device):
    try:
        response = await asyncio.to_thread(
            stream.add_stream, stream_path, model_path, target_device
        )
        return JSONResponse(content={"status": "Success", "metadata": response})
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Error adding pipeline: {str(e)}",
        )


@app.get("/pipeline/metadata/{file_path:path}", tags=["Pipelines"], summary="View pipeline metadata")
async def view_pipeline_metadata(file_path: str = ""):
    try:
        file_path = "/tmp/results.jsonl"
        metadata = await asyncio.to_thread(stream.view_metadata, file_path)
        return JSONResponse(content={"status": "Success", "metadata": metadata})
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Error viewing pipeline metadata: {str(e)}",
        )


@app.delete("/pipeline/{stream_id}", tags=["Pipelines"], summary="Delete a pipeline")
async def delete_pipeline(stream_id: str):
    try:
        result = await asyncio.to_thread(stream.delete_stream, stream_id)
        return JSONResponse(content={"status": "Success", "message": result["message"]})
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Error deleting pipeline: {str(e)}",
        )


@app.get("/metadata/{file_path:path}", tags=["Metadata"], summary="Get metadata from file")
async def get_metadata(file_path: str):
    try:
        decoded_path = unquote(file_path)
        metadata = await asyncio.to_thread(stream.view_metadata, decoded_path)
        return JSONResponse(content={"status": "Success", "metadata": metadata})
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Error getting metadata: {str(e)}",
        )


@app.get("/stream/{stream_id}", tags=["Stream"], summary="Get stream_url")
async def get_stream(stream_id: str):
    try:
        stream_url = await asyncio.to_thread(stream.view_stream, stream_id)
        return JSONResponse(content={"status": "Success", "metadata": stream_url})
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Error accessing stream of id {stream_id}. {e}"
        )


if __name__ == "__main__":
    uvicorn.run("app", host="0.0.0.0", port=8888)
