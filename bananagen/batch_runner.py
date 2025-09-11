import asyncio
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
import time
import logging

from .gemini_adapter import call_gemini

logger = logging.getLogger(__name__)


@dataclass
class BatchJob:
    id: str
    prompt: str
    width: int
    height: int
    output_path: str
    model: str
    template_path: Optional[str] = None
    provider: str = "gemini"


@dataclass
class BatchResult:
    job_id: str
    success: bool
    output_path: Optional[str] = None
    metadata: Optional[dict] = None
    error: Optional[str] = None


class BatchRunner:
    def __init__(self, concurrency: int = 3, rate_limit: float = 1.0):
        self.concurrency = concurrency
        self.rate_limit = rate_limit
        self.semaphore = asyncio.Semaphore(concurrency)
        self.last_request_time = 0.0

    async def process_batch(self, jobs: List[BatchJob]) -> List[BatchResult]:
        """Process a batch of jobs with concurrency and rate limiting."""
        try:
            if not jobs:
                logger.warning("No jobs provided to batch runner")
                return []

            logger.info("Starting batch processing", extra={
                "job_count": len(jobs),
                "concurrency": self.concurrency,
                "rate_limit": self.rate_limit
            })

            tasks = []
            for job in jobs:
                task = asyncio.create_task(self._process_single_job(job))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions carefully
            processed_results = []
            for i, result in enumerate(results):
                job = jobs[i]
                if isinstance(result, Exception):
                    error_msg = f"Task failed: {str(result)}"
                    logger.error("Batch job task failed", extra={
                        "job_id": job.id,
                        "error": str(result),
                        "error_type": type(result).__name__
                    })
                    processed_results.append(BatchResult(
                        job_id=job.id,
                        success=False,
                        error=error_msg
                    ))
                else:
                    processed_results.append(result)

            successful = sum(1 for r in processed_results if r.success)
            failed = len(processed_results) - successful

            logger.info("Batch processing completed", extra={
                "total_jobs": len(jobs),
                "successful": successful,
                "failed": failed
            })

            return processed_results

        except Exception as e:
            logger.error("Batch processing failed critically", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "job_count": len(jobs) if jobs else 0
            })
            # Return empty results on critical failure
            return []

    async def _process_single_job(self, job: BatchJob) -> BatchResult:
        """Process a single job with rate limiting."""
        async with self.semaphore:
            try:
                logger.info("Processing batch job", extra={"job_id": job.id, "prompt": job.prompt[:30] + '...' if len(job.prompt) > 30 else job.prompt})

                # Rate limiting
                now = time.time()
                time_since_last = now - self.last_request_time
                if time_since_last < self.rate_limit:
                    wait_time = self.rate_limit - time_since_last
                    logger.debug("Rate limiting", extra={"job_id": job.id, "wait_time": wait_time})
                    await asyncio.sleep(wait_time)
                self.last_request_time = time.time()

                try:
                    # Generate placeholder if no template
                    if not job.template_path:
                        from .core import generate_placeholder
                        template_path = job.output_path.replace('.png', '_template.png')
                        logger.info("Generating placeholder for batch job", extra={"job_id": job.id, "template_path": template_path})
                        generate_placeholder(job.width, job.height, out_path=template_path)
                    else:
                        template_path = job.template_path
                        logger.debug("Using existing template", extra={"job_id": job.id, "template_path": template_path})

                    # Validate template exists
                    if not Path(template_path).exists():
                        raise FileNotFoundError(f"Template file not found: {template_path}")

                    # Call Gemini
                    logger.debug("Calling Gemini for batch job", extra={"job_id": job.id, "provider": job.provider})
                    generated_path, metadata = await call_gemini(template_path, job.prompt, provider=job.provider)

                    # Validate generated file
                    if not generated_path or not Path(generated_path).exists():
                        raise Exception("Generated file not found after Gemini call")

                    # Copy to output path safely
                    import shutil
                    try:
                        shutil.copy(generated_path, job.output_path)
                        logger.info("Batch job completed successfully", extra={
                            "job_id": job.id,
                            "output_path": job.output_path
                        })
                    except OSError as copy_error:
                        raise Exception(f"Failed to copy generated file to output path: {copy_error}")

                    return BatchResult(
                        job_id=job.id,
                        success=True,
                        output_path=job.output_path,
                        metadata=metadata
                    )

                except Exception as job_error:
                    error_msg = f"Job processing failed: {str(job_error)}"
                    logger.error("Batch job failed", extra={
                        "job_id": job.id,
                        "error": str(job_error),
                        "error_type": type(job_error).__name__,
                        "template_path": getattr(job, 'template_path', 'None')
                    })
                    return BatchResult(
                        job_id=job.id,
                        success=False,
                        error=error_msg
                    )

            except Exception as semaphore_error:
                error_msg = f"Semaphore/concurency error: {str(semaphore_error)}"
                logger.error("Batch job semaphore error", extra={
                    "job_id": job.id,
                    "error": str(semaphore_error),
                    "error_type": type(semaphore_error).__name__
                })
                return BatchResult(
                    job_id=job.id,
                    success=False,
                    error=error_msg
                )
