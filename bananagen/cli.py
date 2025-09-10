import click
import logging
import os
import hashlib
from pathlib import Path
from datetime import datetime
from .core import generate_placeholder
from .gemini_adapter import call_gemini
from .logging_config import configure_logging
from .db import Database

logger = logging.getLogger(__name__)

def validate_positive_int(value: str, param_name: str) -> int:
    """Validate that value is a positive integer."""
    try:
        int_value = int(value)
        if int_value <= 0:
            raise click.BadParameter(f"{param_name} must be a positive integer")
        return int_value
    except ValueError:
        raise click.BadParameter(f"{param_name} must be a positive integer")

def validate_file_path(value: str, must_exist: bool = False) -> str:
    """Validate file path exists or its directory can be created."""
    if not value:
        raise click.BadParameter("File path cannot be empty")

    path = Path(value)

    if must_exist and not path.exists():
        raise click.BadParameter(f"File does not exist: {value}")

    # Check if directory can be created
    if not must_exist:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Test if we can create the file (by trying to touch it)
            if not path.exists():
                path.touch()
                path.unlink()  # Remove the test file
        except (OSError, PermissionError) as e:
            raise click.BadParameter(f"Cannot create file at path {value}: {e}")

    return value

def validate_rate_limit(value: str) -> float:
    """Validate rate limit is positive."""
    try:
        float_value = float(value)
        if float_value <= 0:
            raise click.BadParameter("Rate limit must be positive")
        return float_value
    except ValueError:
        raise click.BadParameter("Rate limit must be a positive number")

def validate_concurrency(value: str) -> int:
    """Validate concurrency is positive integer."""
    return validate_positive_int(value, "Concurrency")

@click.group()
@click.option('--log-level', default='INFO', help='Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
def main(log_level):
    """Bananagen CLI"""
    try:
        # Validate environment variables
        if not os.getenv('NANO_BANANA_API_KEY') and not os.getenv('GEMINI_API_KEY'):
            logger.warning("No API key found. Set NANO_BANANA_API_KEY or GEMINI_API_KEY environment variable for real API access.")
        configure_logging(log_level)
        logger.info("CLI initialized", extra={"log_level": log_level})
    except Exception as e:
        logger.error("Failed to initialize CLI", extra={"error": str(e)})
        raise click.ClickException(f"Failed to initialize CLI: {e}")

@main.command()
@click.option('--width', required=True, help='Image width', callback=lambda ctx, param, value: validate_positive_int(value, 'width'))
@click.option('--height', required=True, help='Image height', callback=lambda ctx, param, value: validate_positive_int(value, 'height'))
@click.option('--color', default='#ffffff', help='Background color')
@click.option('--transparent', is_flag=True, help='Make background transparent')
@click.option('--out', 'out_path', required=True, help='Output file path', callback=lambda ctx, param, value: validate_file_path(value))
def placeholder(width, height, color, transparent, out_path):
    """Generate placeholder images"""
    try:
        logger.info("Starting placeholder generation", extra={
            "width": width,
            "height": height,
            "color": color,
            "transparent": transparent,
            "out_path": out_path
        })

        generate_placeholder(width, height, color, transparent, out_path)

        logger.info("Placeholder generation completed", extra={"out_path": out_path})
        click.echo(f"Placeholder saved to {out_path}")
    except Exception as e:
        logger.error("Placeholder generation failed", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "width": width,
            "height": height,
            "out_path": out_path
        })
        click.echo(f"Error generating placeholder: {e}", err=True)
        raise click.ClickException(f"Failed to generate placeholder: {e}")

@main.command()
@click.option('--placeholder', 'template_path', help='Placeholder image path', callback=lambda ctx, param, value: validate_file_path(value, must_exist=True) if value else None)
@click.option('--prompt', required=True, help='Generation prompt')
@click.option('--width', help='Image width (if no placeholder)', callback=lambda ctx, param, value: validate_positive_int(value, 'width') if value else None)
@click.option('--height', help='Image height (if no placeholder)', callback=lambda ctx, param, value: validate_positive_int(value, 'height') if value else None)
@click.option('--out', 'out_path', required=True, help='Output file path', callback=lambda ctx, param, value: validate_file_path(value))
@click.option('--json', is_flag=True, help='Output JSON')
@click.option('--force', is_flag=True, help='Force re-generation even if cached result exists')
@click.option('--seed', type=int, help='Optional integer seed for reproducible Gemini generation')
def generate(template_path, prompt, width, height, out_path, json, force, seed):
    """Generate images using Gemini"""
    import asyncio
    import uuid
    from datetime import datetime

    if not prompt or not prompt.strip():
        raise click.BadParameter("Prompt cannot be empty")

    logger.info("Starting generate command", extra={
        "template_path": template_path,
        "prompt": prompt[:50] + '...' if len(prompt) > 50 else prompt,
        "width": width,
        "height": height,
        "out_path": out_path,
        "json": json,
        "force": force,
        "seed": seed
    })

    async def _generate():
        generation_id = str(uuid.uuid4())

        logger.info("Initializing generation", extra={"generation_id": generation_id})

        # Initialize template_path for proper scoping
        template_path = template_path
        force = force
        seed = seed

        try:
            # Generate placeholder if needed
            if not template_path:
                template_path = out_path.replace(".png", "_placeholder.png")
                logger.info("Generating placeholder image", extra={"template_path": template_path, "width": width or 512, "height": height or 512})
                generate_placeholder(width or 512, height or 512, out_path=template_path)

            # Compute SHA256 for caching
            with open(template_path, 'rb') as f:
                template_bytes = f.read()
            params_dict = {"seed": seed} if seed is not None else {}
            sha_input = prompt.encode('utf-8') + template_bytes + str(params_dict).encode('utf-8')
            input_sha = hashlib.sha256(sha_input).hexdigest()

            logger.info("Computed input SHA", extra={"input_sha": input_sha, "template_path": template_path})

            # Check cache
            db = Database("bananagen.db")
            cached_generation = db.get_generation_by_sha(input_sha)
            if cached_generation and not force:
                logger.info("Cache hit, using cached result", extra={"cached_generation_id": cached_generation.id, "cached_output_path": cached_generation.output_path})
                import shutil
                shutil.copy(cached_generation.output_path, out_path)
                # For JSON, use cached metadata
                if json:
                    import json as json_lib
                    cached_metadata = cached_generation.metadata or {}
                    cached_metadata["input_sha256"] = input_sha
                    click.echo(json_lib.dumps({
                        "id": cached_generation.id,
                        "status": "cached",
                        "out_path": out_path,
                        "created_at": cached_generation.created_at.isoformat(),
                        "sha256": cached_metadata.get("sha256", ""),
                        "input_sha256": input_sha
                    }))
                else:
                    click.echo(f"Using cached image saved to {out_path}")

                logger.info("Cached generation completed", extra={
                    "generation_id": cached_generation.id,
                    "out_path": out_path,
                    "status": "cached"
                })
                return

            # Cache miss or force, proceed with generation
            logger.info("Cache miss, generating new", extra={"input_sha": input_sha, "force": force})

            # Create GenerationRecord and save to DB
            record = GenerationRecord(
                id=generation_id,
                prompt=prompt,
                width=width or 512,
                height=height or 512,
                output_path=out_path,
                model="gemini-2.5-flash",  # default
                status="processing",
                created_at=datetime.now(),
                sha256=input_sha
            )
            db.save_generation(record)

            logger.info("Calling Gemini API", extra={"generation_id": generation_id, "template_path": template_path, "params": params_dict})
            generated_path, metadata = await call_gemini(template_path, prompt, params=params_dict)

            # For now, just copy to out_path
            import shutil
            logger.info("Copying generated file", extra={"generation_id": generation_id, "generated_path": generated_path, "out_path": out_path})
            shutil.copy(generated_path, out_path)

            # Update metadata with input SHA
            metadata = metadata or {}
            metadata["input_sha256"] = input_sha

            # Update DB record with completion
            db.update_generation_status(generation_id, status="done", metadata=metadata)

            if json:
                import json as json_lib
                click.echo(json_lib.dumps({
                    "id": generation_id,
                    "status": "done",
                    "out_path": out_path,
                    "created_at": datetime.now().isoformat(),
                    "sha256": metadata["sha256"],
                    "input_sha256": input_sha
                }))
            else:
                click.echo(f"Generated image saved to {out_path}")

            logger.info("Generation completed successfully", extra={
                "generation_id": generation_id,
                "out_path": out_path,
                "sha256": metadata["sha256"],
                "input_sha256": input_sha
            })
        except Exception as e:
            logger.error("Generation failed", extra={
                "generation_id": generation_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "template_path": template_path,
                "out_path": out_path
            })
            click.echo(f"Error generating image: {e}", err=True)
            raise click.ClickException(f"Failed to generate image: {e}")

    try:
        asyncio.run(_generate())
    except Exception as e:
        logger.error("Async generation failed", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise click.ClickException(f"Generation process failed: {e}")

# Add other subcommands as placeholders
@main.command()
@click.option('--list', 'jobs_file', required=True, help='JSON file with batch jobs', callback=lambda ctx, param, value: validate_file_path(value, must_exist=True))
@click.option('--concurrency', default=3, help='Number of concurrent jobs', callback=lambda ctx, param, value: validate_concurrency(value))
@click.option('--rate-limit', default=1.0, help='Rate limit between requests', callback=lambda ctx, param, value: validate_rate_limit(value))
@click.option('--json', is_flag=True, help='Output JSON results')
def batch(jobs_file, concurrency, rate_limit, json):
    """Batch processing"""
    import json as json_lib
    import asyncio
    import uuid
    from .batch_runner import BatchRunner, BatchJob

    logger.info("Starting batch processing", extra={
        "jobs_file": jobs_file,
        "concurrency": concurrency,
        "rate_limit": rate_limit,
        "json": json
    })

    async def _batch():
        try:
            # Load jobs from JSON
            logger.info("Loading jobs from file", extra={"jobs_file": jobs_file})
            with open(jobs_file, 'r') as f:
                jobs_data = json_lib.load(f)

            logger.info("Loaded jobs data", extra={"job_count": len(jobs_data)})

            # Validate jobs data structure
            if not isinstance(jobs_data, list):
                raise ValueError("Jobs file must contain a list of jobs")

            # Convert to BatchJob objects with validation
            jobs = []
            for i, job_data in enumerate(jobs_data):
                try:
                    if not isinstance(job_data, dict):
                        raise ValueError(f"Job {i} must be a dictionary")

                    if 'prompt' not in job_data:
                        raise ValueError(f"Job {i} missing required 'prompt' field")
                    if 'output_path' not in job_data:
                        raise ValueError(f"Job {i} missing required 'output_path' field")

                    # Validate prompt
                    if not job_data['prompt'] or not str(job_data['prompt']).strip():
                        raise ValueError(f"Job {i} has empty prompt")

                    # Validate output path
                    validate_file_path(job_data['output_path'])

                    job = BatchJob(
                        id=job_data.get('id', str(uuid.uuid4())),  # Use existing ID or generate new
                        prompt=str(job_data['prompt']),
                        width=validate_positive_int(str(job_data.get('width', 512)), 'width'),
                        height=validate_positive_int(str(job_data.get('height', 512)), 'height'),
                        output_path=job_data['output_path'],
                        model=job_data.get('model', 'gemini-2.5-flash'),
                        template_path=job_data.get('template_path')
                    )
                    jobs.append(job)
                except Exception as e:
                    logger.warning(f"Skipping invalid job {i}", extra={"error": str(e)})
                    continue

            if not jobs:
                raise ValueError("No valid jobs found in file")

            # Process batch
            logger.info("Initializing batch runner", extra={"concurrency": concurrency, "rate_limit": rate_limit, "valid_jobs": len(jobs)})
            runner = BatchRunner(concurrency=concurrency, rate_limit=rate_limit)
            results = await runner.process_batch(jobs)

            logger.info("Batch processing completed", extra={"result_count": len(results)})

            if json:
                output = []
                for result in results:
                    logger.info("Batch result", extra={
                        "job_id": result.job_id,
                        "success": result.success,
                        "output_path": result.output_path,
                        "error": result.error
                    })
                    output.append({
                        "job_id": result.job_id,
                        "success": result.success,
                        "output_path": result.output_path,
                        "metadata": result.metadata,
                        "error": result.error
                    })
                click.echo(json_lib.dumps(output))
            else:
                for result in results:
                    if result.success:
                        click.echo(f"Job {result.job_id}: Success - {result.output_path}")
                    else:
                        click.echo(f"Job {result.job_id}: Failed - {result.error}")
        except Exception as e:
            logger.error("Batch processing failed", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "jobs_file": jobs_file
            })
            raise click.ClickException(f"Batch processing failed: {e}")

    try:
        asyncio.run(_batch())
    except Exception as e:
        logger.error("Async batch processing failed", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise click.ClickException(f"Batch process failed: {e}")

@main.command()
@click.option('--root', default='.', help='Root directory to scan')
@click.option('--pattern', default='*__placeholder__*', help='File pattern to scan')
@click.option('--replace', is_flag=True, help='Replace placeholders in files')
@click.option('--json', is_flag=True, help='Output JSON results')
def scan(root, pattern, replace, json):
    """Scan and replace"""
    import asyncio
    from .scanner import Scanner

    # Validate root directory exists
    try:
        Path(root).stat()  # Check if path exists
        if not pattern or not pattern.strip():
            raise click.BadParameter("Pattern cannot be empty")
    except OSError:
        raise click.BadParameter(f"Root directory does not exist: {root}")
    except Exception as e:
        raise click.BadParameter(f"Invalid scan parameters: {e}")

    logger.info("Starting file scan", extra={
        "root": root,
        "pattern": pattern,
        "replace": replace,
        "json": json
    })

    async def _scan():
        try:
            scanner = Scanner(root_path=root, pattern=pattern)
            logger.info("Scanning files", extra={"root_path": root, "pattern": pattern})
            matches = scanner.scan_files()
            logger.info("Scan completed", extra={"match_count": len(matches)})

            logger.info("Replacing placeholders", extra={"replace_mode": replace})
            results = await scanner.replace_placeholders(matches, replace=replace)

            logger.info("Replace operation completed", extra={"result_count": len(results)})

            if json:
                import json as json_lib
                click.echo(json_lib.dumps(results))
            else:
                for result in results:
                    if result['status'] == 'replaced':
                        logger.info("File replacement completed", extra={
                            "file": result['file'],
                            "line": result['line'],
                            "generated_path": result['generated_path']
                        })
                        click.echo(f"Replaced in {result['file']}:{result['line']} -> {result['generated_path']}")
                    elif result['status'] == 'generated':
                        logger.info("File generation completed", extra={
                            "file": result['file'],
                            "line": result['line'],
                            "generated_path": result['generated_path']
                        })
                        click.echo(f"Generated for {result['file']}:{result['line']} -> {result['generated_path']}")
                    elif result['status'] == 'skipped':
                        logger.warning("File skipped during replace", extra={
                            "file": result['file'],
                            "line": result['line'],
                            "reason": result['reason']
                        })
                        click.echo(f"Skipped {result['file']}:{result['line']} - {result['reason']}")
                    else:
                        logger.error("Error during replace operation", extra={
                            "file": result['file'],
                            "line": result['line'],
                            "error": result['error']
                        })
                        click.echo(f"Error in {result['file']}:{result['line']} - {result['error']}")
        except Exception as e:
            logger.error("Scan operation failed", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "root": root,
                "pattern": pattern
            })
            raise click.ClickException(f"Scan operation failed: {e}")

    try:
        asyncio.run(_scan())
    except Exception as e:
        logger.error("Async scan failed", extra={
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise click.ClickException(f"Scan process failed: {e}")

@main.command()
@click.option('--port', default=9090, help='Port to serve on', callback=lambda ctx, param, value: validate_positive_int(value, 'port'))
@click.option('--host', default='0.0.0.0', help='Host to bind to')
def serve(port, host):
    """Serve API"""
    from .api import app
    import uvicorn

    try:
        logger.info("Starting API server", extra={"host": host, "port": port})

        click.echo(f"Serving API on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        logger.error("Failed to start API server", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "host": host,
            "port": port
        })
        raise click.ClickException(f"Failed to start API server: {e}")

@main.command()
@click.argument('id')
@click.option('--json', is_flag=True, help='Output JSON')
def status(id, json):
    """Check status"""
    try:
        if not id or not str(id).strip():
            raise click.BadParameter("Job ID cannot be empty")

        from .db import Database

        logger.info("Checking job status", extra={"job_id": id, "json": json})

        db = Database("bananagen.db")

        # Check generation
        gen_record = db.get_generation(id)
        if gen_record:
            logger.info("Found generation record", extra={"job_id": id, "status": gen_record.status})
            if json:
                import json as json_lib
                click.echo(json_lib.dumps({
                    "id": gen_record.id,
                    "status": gen_record.status,
                    "created_at": gen_record.created_at.isoformat(),
                    "completed_at": gen_record.completed_at.isoformat() if gen_record.completed_at else None,
                    "metadata": gen_record.metadata,
                    "error": gen_record.error
                }))
            else:
                click.echo(f"Generation {id}: {gen_record.status}")
                if gen_record.completed_at:
                    click.echo(f"Completed at: {gen_record.completed_at}")
                if gen_record.error:
                    click.echo(f"Error: {gen_record.error}")
            return

        # Check batch
        batch_record = db.get_batch(id)
        if batch_record:
            logger.info("Found batch record", extra={"job_id": id, "status": batch_record.status, "job_count": batch_record.job_count})
            if json:
                import json as json_lib
                click.echo(json_lib.dumps({
                    "id": batch_record.id,
                    "status": batch_record.status,
                    "created_at": batch_record.created_at.isoformat(),
                    "completed_at": batch_record.completed_at.isoformat() if batch_record.completed_at else None,
                    "results": batch_record.results,
                    "error": batch_record.error
                }))
            else:
                click.echo(f"Batch {id}: {batch_record.status} ({batch_record.job_count} jobs)")
                if batch_record.completed_at:
                    click.echo(f"Completed at: {batch_record.completed_at}")
                if batch_record.error:
                    click.echo(f"Error: {batch_record.error}")
            return

        logger.warning("Job not found in database", extra={"job_id": id})
        click.echo(f"Job {id} not found")
    except Exception as e:
        logger.error("Failed to check job status", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "job_id": id
        })
        raise click.ClickException(f"Failed to check job status: {e}")

if __name__ == '__main__':
    main()
