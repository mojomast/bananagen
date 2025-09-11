from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from pathlib import Path
import asyncio
from datetime import datetime, timedelta
import uuid
import time
import logging
import os

from .db import Database, GenerationRecord, BatchRecord, ScanRecord
from .batch_runner import BatchRunner, BatchJob
from .gemini_adapter import call_gemini
from .core import generate_placeholder

logger = logging.getLogger(__name__)

app = FastAPI(title="Bananagen API", version="0.1.0")

# Environment variable validation
def validate_environment():
    """Validate required environment variables."""
    required_vars = []
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        logger.warning("Missing environment variables", extra={
            "missing_vars": missing_vars,
            "details": "Some optional environment variables are missing, but they may be required for certain features."
        })

    api_key_found = os.getenv('NANO_BANANA_API_KEY') or os.getenv('GEMINI_API_KEY')
    if not api_key_found:
        logger.warning("No API key found", extra={
            "details": "Set NANO_BANANA_API_KEY or GEMINI_API_KEY for real API access. Using mock mode."
        })

# Global database instance - initialize with validation
validate_environment()
try:
    db = Database("bananagen.db")
except Exception as e:
    logger.error("Failed to initialize database", extra={"error": str(e)})
    raise

# Add custom exception handler for Pydantic validation errors
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error("Request validation failed", extra={
        "errors": exc.errors(),
        "url": str(request.url),
        "method": request.method,
        "client_ip": request.client.host if request.client else None
    })
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "details": exc.errors(),
            "message": "Request data is invalid. Please check the required fields."
        }
    )

# Add custom exception handler for generic HTTP exceptions
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error("HTTP error occurred", extra={
        "status_code": exc.status_code,
        "detail": exc.detail,
        "url": str(request.url),
        "method": request.method,
        "client_ip": request.client.host if request.client else None
    })
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "message": f"HTTP {exc.status_code}"}
    )

# Rate limiting: 10 requests per minute per IP
RATE_LIMIT = 10
RATE_WINDOW = timedelta(minutes=1)
rate_store = {}

def check_rate_limit(request: Request):
    """
    Validate rate limit for incoming requests.
    """
    try:
        client_ip = request.client.host
        if not client_ip:
            logger.warning("Unable to determine client IP for rate limiting")
            raise HTTPException(status_code=400, detail="Unable to determine client IP")

        now = datetime.now()

        if client_ip not in rate_store:
            rate_store[client_ip] = []

        # Remove old requests outside window
        rate_store[client_ip] = [t for t in rate_store[client_ip] if now - t < RATE_WINDOW]

        if len(rate_store[client_ip]) >= RATE_LIMIT:
            logger.warning("Rate limit exceeded", extra={
                "ip_address": client_ip,
                "request_count": len(rate_store[client_ip]),
                "rate_limit": RATE_LIMIT,
                "window_seconds": RATE_WINDOW.total_seconds()
            })
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {RATE_LIMIT} requests per {int(RATE_WINDOW.total_seconds())} seconds."
            )

        rate_store[client_ip].append(now)
        logger.info("Rate limit check passed", extra={"ip_address": client_ip, "current_count": len(rate_store[client_ip])})
    except Exception as e:
        logger.error("Rate limit check failed", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "client_ip": getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
        })
        raise HTTPException(status_code=500, detail="Rate limiting service error")

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500, description="Generation prompt")
    width: int = Field(512, gt=0, le=4096, description="Image width in pixels")
    height: int = Field(512, gt=0, le=4096, description="Image height in pixels")
    output_path: str = Field(..., description="Output file path")
    model: str = Field("gemini-2.5-flash", pattern=r"^[a-zA-Z0-9\-_\.]+$", description="Model name")
    template_path: Optional[str] = Field(None, description="Optional template image path")
    provider: str = Field("gemini", pattern=r"^(gemini|openrouter|requesty)$", description="AI provider to use")

    @field_validator('prompt')
    @classmethod
    def validate_prompt(cls, v):
        if not v.strip():
            raise ValueError("Prompt cannot be empty or whitespace only")
        return v.strip()

    @field_validator('output_path')
    @classmethod
    def validate_output_path(cls, v):
        if not v:
            raise ValueError("Output path cannot be empty")
        # Check file extension
        if not (v.endswith('.png') or v.endswith('.jpg') or v.endswith('.jpeg')):
            raise ValueError("Output path must have a valid image extension (.png, .jpg, .jpeg)")
        return v

class BatchJobRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500, description="Generation prompt")
    width: int = Field(512, gt=0, le=4096, description="Image width in pixels")
    height: int = Field(512, gt=0, le=4096, description="Image height in pixels")
    output_path: str = Field(..., description="Output file path")
    model: str = Field("gemini-2.5-flash", pattern=r"^[a-zA-Z0-9\-_\.]+$", description="Model name")
    template_path: Optional[str] = Field(None, description="Optional template image path")
    provider: str = Field("gemini", pattern=r"^(gemini|openrouter|requesty)$", description="AI provider to use")
    id: Optional[str] = Field(None, description="Optional job ID")

    @field_validator('prompt')
    @classmethod
    def validate_batch_prompt(cls, v):
        if not v.strip():
            raise ValueError("Prompt cannot be empty or whitespace only")
        return v.strip()

class BatchRequest(BaseModel):
    jobs: List[BatchJobRequest] = Field(..., min_items=1, max_items=100, description="List of generation jobs")

class ScanRequest(BaseModel):
    root: str = Field(".", description="Root directory to scan")
    pattern: str = Field("*__placeholder__*", min_length=1, description="File pattern to scan")
    replace: bool = Field(False, description="Replace placeholders in files")
    extract_from: List[str] = Field(["readme", "manifest"], description="Extract prompts from these sources")

class ConfigureRequest(BaseModel):
    provider: str = Field(..., pattern=r"^(openrouter|requesty)$", description="API provider to configure")
    api_key: str = Field(..., min_length=1, description="API key for the provider")
    environment: str = Field("production", pattern=r"^(development|staging|production)$", description="Environment for configuration")

    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if not v.strip():
            raise ValueError("API key cannot be empty or whitespace only")
        # Basic format validation - should contain alphanumeric and allowed special chars
        import re
        if not re.match(r'^[a-zA-Z0-9\-_\.]+$', v):
            raise ValueError("API key format is invalid")
        return v.strip()

@app.post("/generate")
async def generate_image(request: GenerateRequest, background_tasks: BackgroundTasks, req: Request):
    client_ip = req.client.host
    check_rate_limit(req)
    """Queue an image generation job."""
    generation_id = str(uuid.uuid4())
    
    logger.info("Image generation requested", extra={
        "generation_id": generation_id,
        "prompt": request.prompt[:50] + '...' if len(request.prompt) > 50 else request.prompt,
        "width": request.width,
        "height": request.height,
        "output_path": request.output_path,
        "model": request.model,
        "template_path": request.template_path,
        "provider": request.provider,
        "ip_address": client_ip
    })
    
    # Create record
    record = GenerationRecord(
        id=generation_id,
        prompt=request.prompt,
        width=request.width,
        height=request.height,
        output_path=request.output_path,
        model=request.model,
        status="queued",
        created_at=datetime.now()
    )
    db.save_generation(record)
    
    # Process in background
    background_tasks.add_task(process_generation, generation_id, request)
    
    logger.info("Generation job queued", extra={"generation_id": generation_id})
    
    return {"id": generation_id, "status": "queued", "created_at": record.created_at.isoformat()}

@app.post("/batch")
async def batch_generate(request: BatchRequest, background_tasks: BackgroundTasks, req: Request):
    """Queue a batch of generation jobs."""
    client_ip = req.client.host
    check_rate_limit(req)

    batch_id = str(uuid.uuid4())

    logger.info("Batch generation requested", extra={
        "batch_id": batch_id,
        "job_count": len(request.jobs),
        "ip_address": client_ip
    })

    try:
        # Convert jobs - now using the validated Pydantic model
        jobs = []
        for job_data in request.jobs:
            job = BatchJob(
                id=job_data.id or str(uuid.uuid4()),
                prompt=job_data.prompt,
                width=job_data.width,
                height=job_data.height,
                output_path=job_data.output_path,
                model=job_data.model,
                template_path=job_data.template_path,
                provider=job_data.provider
            )
            jobs.append(job)

        logger.info("Jobs validated and converted", extra={"converted_jobs": len(jobs)})

    except Exception as e:
        logger.error("Failed to convert batch jobs", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "job_count": len(request.jobs)
        })
        raise HTTPException(status_code=400, detail=f"Invalid job data: {e}")

    # Create batch record
    record = BatchRecord(
        id=batch_id,
        job_count=len(jobs),
        status="queued",
        created_at=datetime.now()
    )
    db.save_batch(record)
    
    # Process in background
    background_tasks.add_task(process_batch, batch_id, jobs)
    
    logger.info("Batch job queued", extra={"batch_id": batch_id})
    
    return {"id": batch_id, "status": "queued", "created_at": record.created_at.isoformat()}

@app.get("/status/{item_id}")
async def get_status(item_id: str):
    """Get status of a generation, batch, or scan job."""
    try:
        if not item_id or not str(item_id).strip():
            raise HTTPException(status_code=400, detail="Job ID cannot be empty")

        logger.info("Status check requested", extra={"job_id": item_id})

        # Check generations first
        gen_record = db.get_generation(item_id)
        if gen_record:
            logger.info("Found generation record", extra={"job_id": item_id, "status": gen_record.status})
            return {
                "id": gen_record.id,
                "status": gen_record.status,
                "created_at": gen_record.created_at.isoformat(),
                "completed_at": gen_record.completed_at.isoformat() if gen_record.completed_at else None,
                "metadata": gen_record.metadata,
                "error": gen_record.error
            }

        # Check batches
        batch_record = db.get_batch(item_id)
        if batch_record:
            logger.info("Found batch record", extra={"job_id": item_id, "status": batch_record.status, "job_count": batch_record.job_count})
            return {
                "id": batch_record.id,
                "status": batch_record.status,
                "created_at": batch_record.created_at.isoformat(),
                "completed_at": batch_record.completed_at.isoformat() if batch_record.completed_at else None,
                "results": batch_record.results,
                "error": batch_record.error
            }

        # Check scans
        scan_record = db.get_scan(item_id)
        if scan_record:
            logger.info("Found scan record", extra={"job_id": item_id, "status": scan_record.status})
            return {
                "id": scan_record.id,
                "status": scan_record.status,
                "created_at": scan_record.created_at.isoformat(),
                "completed_at": scan_record.completed_at.isoformat() if scan_record.completed_at else None,
                "metadata": scan_record.metadata,
                "error": scan_record.error
            }

        logger.warning("Job not found", extra={"job_id": item_id})
        raise HTTPException(status_code=404, detail="Job not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job status", extra={
            "job_id": item_id,
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise HTTPException(status_code=500, detail="Internal server error while retrieving job status")


@app.post("/scan")
async def scan_placeholders(request: ScanRequest, background_tasks: BackgroundTasks, req: Request):
    check_rate_limit(req)
    """Queue a placeholder scan job."""
    scan_id = str(uuid.uuid4())

    # Create record
    record = ScanRecord(
        id=scan_id,
        root=request.root,
        pattern=request.pattern,
        replace=request.replace,
        extract_from=request.extract_from,
        status="queued",
        created_at=datetime.now()
    )
    db.save_scan(record)

    # Process in background
    background_tasks.add_task(process_scan, scan_id, request)

    return {"id": scan_id, "status": "queued", "created_at": record.created_at.isoformat()}

# Configure API endpoint
@app.post("/configure")
async def configure_provider(request: ConfigureRequest, req: Request):
    """Configure an API provider with its credentials."""
    client_ip = req.client.host
    check_rate_limit(req)

    logger.info("Provider configuration requested", extra={
        "provider": request.provider,
        "environment": request.environment,
        "ip_address": client_ip
    })

    try:
        # Check if provider already exists
        existing_provider = db.get_api_provider(request.provider)
        if existing_provider:
            raise HTTPException(
                status_code=409,
                detail=f"Provider '{request.provider}' already configured. Use --force to overwrite."
            )

        # Encrypt and save API key
        encrypted_key = db.encrypt_api_key(request.api_key)

        # Save provider configuration
        provider_data = {
            'provider': request.provider,
            'api_key': encrypted_key,
            'environment': request.environment
        }
        db.save_api_provider(provider_data)

        logger.info("Provider configured successfully", extra={
            "provider": request.provider,
            "environment": request.environment
        })

        return {
            "message": f"Provider '{request.provider}' configured successfully.",
            "provider": request.provider,
            "environment": request.environment
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Provider configuration failed", extra={
            "provider": request.provider,
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise HTTPException(status_code=500, detail="Failed to configure provider")

async def process_generation(generation_id: str, request: GenerateRequest):

    try:
        db.update_generation_status(generation_id, "processing")

        # Generate placeholder if needed
        if not request.template_path:
            template_path = request.output_path.replace('.png', '_template.png')
            logger.info("Generating placeholder", extra={
                "generation_id": generation_id,
                "template_path": template_path,
                "width": request.width,
                "height": request.height
            })
            generate_placeholder(request.width, request.height, out_path=template_path)
        else:
            template_path = request.template_path
            logger.info("Using existing template", extra={"generation_id": generation_id, "template_path": template_path})

        # Generate image
        logger.info("Calling Gemini API", extra={"generation_id": generation_id, "provider": request.provider})
        generated_path, metadata = await call_gemini(template_path, request.prompt, provider=request.provider)

        # Copy to output
        import shutil
        logger.info("Copying generated file", extra={
            "generation_id": generation_id,
            "generated_path": generated_path,
            "output_path": request.output_path
        })

        try:
            shutil.copy(generated_path, request.output_path)
            logger.info("File copied successfully", extra={"generation_id": generation_id, "output_path": request.output_path})
        except OSError as e:
            raise Exception(f"Failed to copy generated file: {e}")

        db.update_generation_status(generation_id, "done", metadata=metadata)
        logger.info("Generation completed successfully", extra={
            "generation_id": generation_id,
            "output_path": request.output_path
        })

    except Exception as e:
        error_msg = f"Generation failed: {str(e)}"
        logger.error("Generation failed", extra={
            "generation_id": generation_id,
            "error": str(e),
            "error_type": type(e).__name__,
            "prompt": request.prompt[:30] + '...' if len(request.prompt) > 30 else request.prompt
        })
        db.update_generation_status(generation_id, "failed", error=error_msg)

async def process_batch(batch_id: str, jobs: List[BatchJob]):
    """Process a batch of jobs."""
    try:
        db.update_batch_status(batch_id, "processing")

        runner = BatchRunner(concurrency=3, rate_limit=1.0)
        results = await runner.process_batch(jobs)

        # Convert results to dict
        results_dict = []
        for result in results:
            results_dict.append({
                "job_id": result.job_id,
                "success": result.success,
                "output_path": result.output_path,
                "metadata": result.metadata,
                "error": result.error
            })

        db.update_batch_status(batch_id, "done", results=results_dict)
    except Exception as e:
        db.update_batch_status(batch_id, "failed", error=str(e))

async def process_scan(scan_id: str, request: ScanRequest):
    """Process a scan job."""
    try:
        db.update_scan_status(scan_id, "processing")

        from .scanner import Scanner

        scanner = Scanner(root_path=request.root, pattern=request.pattern)
        matches = scanner.scan_files()

        results = await scanner.replace_placeholders(matches, replace=request.replace)

        # Count results
        replaced = sum(1 for r in results if r["status"] == "replaced")
        errors = sum(1 for r in results if r["status"] == "error")

        metadata = {
            "replaced": replaced,
            "errors": errors,
            "details": results
        }

        db.update_scan_status(scan_id, "done", metadata=metadata)
    except Exception as e:
        db.update_scan_status(scan_id, "failed", error=str(e))
