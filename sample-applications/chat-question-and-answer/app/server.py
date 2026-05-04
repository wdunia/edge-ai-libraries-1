# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import inspect
import json
import logging
import time
import uvicorn
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse, JSONResponse
from .chain import process_chunks
from .metrics import SystemMonitor
import httpx
from typing import List
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI(title="Chat Question and Answer", root_path="/v1/chatqna")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(
        ","
    ),  # Adjust this to your needs
    allow_credentials=True,
    allow_methods=os.getenv("CORS_ALLOW_METHODS", "*").split(","),
    allow_headers=os.getenv("CORS_ALLOW_HEADERS", "*").split(","),
)

# health check LLM model server
async def check_server_health(host, server_type):
    if host.startswith(("vllm", "text", "tei")):
        return await check_health(f"http://{host}/health", server_type)
    elif host.startswith(("ovms", "openvino")):
        return await check_health(f"http://{host}/v2/health/ready", server_type)
    else:
        raise HTTPException(status_code=503, detail=f"Unknown server type for {server_type}")

async def check_health(url, server_type):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                return {"status": "healthy", "details": f"{server_type} is ready to serve"}
            else:
                raise HTTPException(status_code=503, detail=f"{server_type} is not ready to accept connections, please try after a few minutes")
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail=f"{server_type} is not ready to accept connections, please try after a few minutes")

@app.get("/")
async def redirect_root_to_docs():
    return RedirectResponse("/docs")


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class QuestionRequest(BaseModel):
    conversation_messages: List[Message]
    max_tokens: int
    
class TimedStreamingResponse(StreamingResponse):
    def __init__(self, content, **kwargs):
        self.start_time = time.time()
        self.end_time = None
        super().__init__(content, **kwargs)


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify if the LLM and embedding model servers are ready to serve connections.

    Returns:
        The status of the LLM and embedding model servers.
    """
    endpoint_url = os.getenv("ENDPOINT_URL")
    embedding_endpoint = os.getenv("EMBEDDING_ENDPOINT_URL")

    if not endpoint_url or not embedding_endpoint:
        raise HTTPException(status_code=503, detail="ENDPOINT_URL or EMBEDDING_ENDPOINT_URL is not set")

    result = []
    model_host = endpoint_url.split("//")[-1].split("/")[0].lower()
    #health check LLM model server
    result.append(await check_server_health(model_host, "LLM model server"))

    embed_host = embedding_endpoint.split("//")[-1].split("/")[0].lower()
    #health check Embedding model server
    result.append(await check_server_health(embed_host, "Embedding model server"))    
    
    if any(status["status"] != "healthy" for status in result):
        raise HTTPException(status_code=503, detail=f"LLM/Embedding model server is not ready")

    return result

@app.get("/model")
async def get_llm_model():
    """
    Endpoint to get the current LLM model.

    Returns:
        The current LLM model.
    """
    llm_model = os.getenv("LLM_MODEL")
    if not llm_model:
        raise HTTPException(status_code=503, detail="LLM_MODEL is not set")
    return {"status": "success", "llm_model": llm_model}



async def add_timing_to_generator(generator_func, *args, **kwargs):
    """Add timing to a generator function"""
    start_time = time.time()
    
    async def timed_generator():
        last_chunk_time = start_time
        
        try:
            async for chunk in generator_func(*args, **kwargs):
                last_chunk_time = time.time()
                yield chunk
            
            # Add timing info
            total_time = round((last_chunk_time - start_time) * 1000, 2)
            timing_data = f"data: {json.dumps({'response_time_ms': total_time, 'finished': True})}\n\n"
            yield timing_data
            
        except Exception as e:
            error_time = time.time()
            error_response_time = round((error_time - start_time) * 1000, 2)
            error_data = f"data: {json.dumps({'error': str(e), 'response_time_ms': error_response_time})}\n\n"
            yield error_data
    
    return timed_generator()

@app.post("/chat", response_class=StreamingResponse)
async def query_chain(payload: QuestionRequest):
    try:
        conversation_messages = payload.conversation_messages
        logging.info(conversation_messages)
        question_text = conversation_messages[-1].content

        max_tokens = payload.max_tokens if payload.max_tokens else 512
        if max_tokens > 1024:
            raise HTTPException(status_code=422, detail="max tokens cannot be greater than 1024")
        if not question_text or question_text == "":
            raise HTTPException(status_code=422, detail="Question is required")
        
        if len(question_text.strip()) == 0:
            raise HTTPException(status_code=422, detail="Question cannot be empty or whitespace only")
        
        # Add timing to the generator
        timed_generator = await add_timing_to_generator(
            process_chunks, 
            conversation_messages, 
            max_tokens
        )
        
        return StreamingResponse(timed_generator, media_type="text/event-stream")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

  
    
@app.get("/metrics", tags=["metrics"], summary="Get system metrics")
async def get_system_metrics(ram_type: str = "percent"):

    try:
        monitor = SystemMonitor()
        return StreamingResponse(monitor.return_all(), media_type="text/event-stream")
        
    
    except Exception as e:
        logging.error(f"Error getting system metrics. {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting system metrics: {str(e)}",
        )
    

FastAPIInstrumentor.instrument_app(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
