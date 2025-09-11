import click
import logging
import os
import hashlib
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from .core import generate_placeholder, encrypt_key
from .gemini_adapter import call_gemini
from .logging_config import configure_logging
from .db import Database, GenerationRecord, APIProviderRecord, APIKeyRecord
from .models.api_provider import APIProvider
from .models.api_key import APIKey

# Load environment variables from .env file
load_dotenv()

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

def validate_endpoint_url(value: str) -> str:
    """Validate that value is a valid URL endpoint."""
    if not value or not value.strip():
        raise click.BadParameter("Endpoint URL cannot be empty")

    value = value.strip()

    # Basic URL pattern validation
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(value):
        raise click.BadParameter(f"Invalid endpoint URL format: {value}. Must be a valid HTTP/HTTPS URL.")

    return value

def validate_model_name(value: str) -> str:
    """Validate model name is non-empty."""
    if not value or not value.strip():
        raise click.BadParameter("Model name cannot be empty")
    return value.strip()

def get_provider_choice() -> str:
    """Get user's choice for provider configuration."""
    click.echo("\nProvider Configuration:")
    click.echo("1. Configure a new provider")
    click.echo("2. Update an existing provider")

    choice = click.prompt("Choose an option", type=click.Choice(['1', '2']), show_choices=False)
    return choice

def list_existing_providers(db: Database) -> Optional[str]:
    """List existing providers and let user choose one to update."""
    providers = db.list_active_api_providers()

    if not providers:
        click.echo("No existing providers found.")
        return None

    click.echo("\nAvailable providers:")
    for i, provider in enumerate(providers, 1):
        click.echo(f"{i}. {provider.display_name} ({provider.name}) - {provider.endpoint_url}")

    choice = click.prompt(
        f"Choose a provider to update (1-{len(providers)})",
        type=click.IntRange(1, len(providers))
    )

    return providers[choice - 1].name

def prompt_provider_details(existing_provider: Optional[APIProviderRecord] = None) -> Dict[str, Any]:
    """Prompt user for provider configuration details."""
    if existing_provider:
        click.echo(f"\nUpdating provider: {existing_provider.display_name}")

        # Use existing values as defaults
        current_name = existing_provider.name
        current_endpoint = existing_provider.endpoint_url
        current_model = existing_provider.model_name or ""
        current_base_url = existing_provider.base_url or current_endpoint
    else:
        current_name = current_endpoint = current_model = current_base_url = ""

    # Provider name
    provider_name = click.prompt(
        "Provider name",
        default=current_name,
        value_proc=lambda x: x.strip().lower()
    ).strip().lower()

    if not provider_name:
        raise click.BadParameter("Provider name cannot be empty")

    # Validate provider name format to prevent SQL injection and other issues
    if not re.match(r'^[a-z0-9_-]+$', provider_name):
        raise click.BadParameter("Provider name can only contain lowercase letters, numbers, hyphens, and underscores")

    # Endpoint URL
    endpoint_url = click.prompt(
        "Endpoint URL",
        default=current_endpoint,
        value_proc=validate_endpoint_url
    )

    # Model name
    model_name = click.prompt(
        "Model name",
        default=current_model,
        value_proc=validate_model_name
    )

    # Base URL (optional)
    base_url = click.prompt(
        "Base URL (leave empty for same as endpoint)",
        default=current_base_url if current_base_url != current_endpoint else "",
        show_default=False
    ).strip()

    if not base_url:
        base_url = endpoint_url

    return {
        'name': provider_name,
        'display_name': provider_name.title(),
        'endpoint_url': endpoint_url,
        'model_name': model_name,
        'base_url': base_url,
        'auth_type': 'bearer'  # Default auth type
    }

def prompt_api_key() -> str:
    """Prompt for API key with confirmation."""
    import getpass

    while True:
        api_key = getpass.getpass("Enter API key: ")
        if not api_key or not api_key.strip():
            click.echo("API key cannot be empty. Please try again.")
            continue

        # Basic API key validation - should only contain safe characters
        api_key = api_key.strip()

        if len(api_key) < 10:
            click.echo("API key seems too short (less than 10 characters). Please verify and try again.")
            continue

        confirm_key = getpass.getpass("Confirm API key: ")
        if api_key == confirm_key:
            return api_key
        else:
            click.echo("API keys don't match. Please try again.")
            if not click.confirm("Try entering the API key again?"):
                raise click.Abort()

def confirm_configuration(details: Dict[str, Any]) -> bool:
    """Show configuration summary and ask for confirmation."""
    click.echo("\nConfiguration Summary:")
    click.echo(f"  Provider: {details['display_name']} ({details['name']})")
    click.echo(f"  Endpoint: {details['endpoint_url']}")
    click.echo(f"  Model: {details['model_name']}")
    click.echo(f"  Base URL: {details['base_url']}")
    click.echo(f"  Auth Type: {details['auth_type']}")

    return click.confirm("Do you want to save this configuration?")

@click.group()
@click.option('--log-level', default='INFO', help='Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
def main(log_level):
    """Bananagen CLI"""
    try:
        # Check for API keys in environment variables
        has_env_keys = bool(
            os.getenv('REQUESTY_API_KEY') or 
            os.getenv('OPENROUTER_API_KEY') or 
            os.getenv('GEMINI_API_KEY') or 
            os.getenv('NANO_BANANA_API_KEY')
        )
        
        if not has_env_keys:
            logger.warning("No API keys found in environment. Set API keys in .env file for real API access.")
        else:
            # Log which providers are configured
            configured = []
            if os.getenv('REQUESTY_API_KEY'):
                configured.append('requesty')
            if os.getenv('OPENROUTER_API_KEY'):
                configured.append('openrouter')
            if os.getenv('GEMINI_API_KEY') or os.getenv('NANO_BANANA_API_KEY'):
                configured.append('gemini')
            logger.info(f"API providers configured via .env: {', '.join(configured)}")
        
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
@click.option('--provider', type=click.Choice(['requesty', 'openrouter']), help='AI provider to use for generation (auto-selects if not specified)')
@click.option('--placeholder', 'template_path', help='Placeholder image path', callback=lambda ctx, param, value: validate_file_path(value, must_exist=True) if value else None)
@click.option('--prompt', required=True, help='Generation prompt')
@click.option('--width', help='Image width (if no placeholder)', callback=lambda ctx, param, value: validate_positive_int(value, 'width') if value else None)
@click.option('--height', help='Image height (if no placeholder)', callback=lambda ctx, param, value: validate_positive_int(value, 'height') if value else None)
@click.option('--out', 'out_path', required=True, help='Output file path', callback=lambda ctx, param, value: validate_file_path(value))
@click.option('--json', is_flag=True, help='Output JSON')
@click.option('--force', is_flag=True, help='Force re-generation even if cached result exists')
@click.option('--seed', type=int, help='Optional integer seed for reproducible Gemini generation')
def generate(provider, template_path, prompt, width, height, out_path, json, force, seed):
    """Generate images using selected AI provider"""
    import asyncio
    import uuid
    from datetime import datetime

    if not prompt or not prompt.strip():
        raise click.BadParameter("Prompt cannot be empty")

    # Set default provider if not specified - commenting out Gemini for now
    if provider is None:
        provider = 'openrouter'  # Changed from 'requesty' to 'openrouter'

    logger.info("Starting generate command", extra={
        "provider": provider,
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
        from .db import Database
        generation_id = str(uuid.uuid4())

        logger.info("Initializing generation", extra={"generation_id": generation_id})

        try:
            # Auto-select provider - Gemini commented out for now
            selected_provider = provider
            # if provider == 'gemini' and not (os.getenv('NANO_BANANA_API_KEY') or os.getenv('GEMINI_API_KEY')):
            #     # Try to find a configured provider
            #     db = Database("bananagen.db")
            #     try:
            #         providers = db.list_active_api_providers()
            #         for prov in providers:
            #             if prov.is_active and prov.name in ['openrouter', 'requesty']:
            #                 api_keys = db.get_api_keys_for_provider(prov.id)
            #                 if api_keys:
            #                     selected_provider = prov.name
            #                     logger.info("Auto-selected configured provider", extra={"provider": selected_provider})
            #                     break
            #     except Exception as e:
            #         logger.debug("Could not auto-select provider", extra={"error": str(e)})
            
            # Validate provider and check configuration - Gemini commented out
            if selected_provider not in ['openrouter', 'requesty']:  # removed 'gemini'
                raise click.BadParameter(f"Unsupported provider '{selected_provider}'. Supported providers: openrouter, requesty")
    
            # Check if provider is configured - check environment variables first
            env_api_key = None
            if selected_provider == 'openrouter':
                env_api_key = os.getenv('OPENROUTER_API_KEY')
            elif selected_provider == 'requesty':
                env_api_key = os.getenv('REQUESTY_API_KEY')
            
            if not env_api_key:
                # No environment variable, check database
                db = Database("bananagen.db")
                try:
                    provider_record = db.get_api_provider(selected_provider)
                    if not provider_record:
                        raise click.ClickException(f"Error: Provider '{selected_provider}' not configured. Run 'bananagen configure --provider {selected_provider}' to set up API key.")

                    api_keys = db.get_api_keys_for_provider(provider_record.id)
                    if not api_keys:
                        raise click.ClickException(f"Error: Provider '{selected_provider}' not configured. Run 'bananagen configure --provider {selected_provider}' to set up API key.")
                except Exception as e:
                    if "not configured" not in str(e):
                        logger.error("Database error checking provider configuration", extra={"provider": selected_provider, "error": str(e)})
                        raise click.ClickException(f"Error: Unable to verify provider configuration: {e}")            # Generate placeholder if needed
            actual_template_path = template_path
            if not actual_template_path:
                actual_template_path = out_path.replace(".png", "_placeholder.png")
                logger.info("Generating placeholder image", extra={"template_path": actual_template_path, "width": width or 512, "height": height or 512})
                generate_placeholder(width or 512, height or 512, out_path=actual_template_path)
    
            # Compute SHA256 for caching
            with open(actual_template_path, 'rb') as f:
                template_bytes = f.read()
            params_dict = {"seed": seed} if seed is not None else {}
            sha_input = prompt.encode('utf-8') + template_bytes + str(params_dict).encode('utf-8')
            input_sha = hashlib.sha256(sha_input).hexdigest()

            logger.info("Computed input SHA", extra={"input_sha": input_sha, "template_path": actual_template_path, "provider": provider})            # Check cache
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
                    cached_metadata["provider"] = selected_provider
                    click.echo(json_lib.dumps({
                        "id": cached_generation.id,
                        "status": "cached",
                        "out_path": out_path,
                        "provider": selected_provider,
                        "created_at": cached_generation.created_at.isoformat(),
                        "sha256": cached_metadata.get("sha256", ""),
                        "input_sha256": input_sha
                    }))
                else:
                    click.echo(f"Using cached image saved to {out_path}")
    
                logger.info("Cached generation completed", extra={
                    "generation_id": cached_generation.id,
                    "out_path": out_path,
                    "status": "cached",
                    "provider": selected_provider
                })
                return
    
            # Cache miss or force, proceed with generation
            logger.info("Cache miss, generating new", extra={"input_sha": input_sha, "force": force, "provider": selected_provider})
    
            # Provider adapters are now implemented - Gemini commented out for now

            # Determine model based on provider - Gemini commented out
            if selected_provider == 'openrouter':
                model_name = os.getenv('OPENROUTER_MODEL', 'google/gemini-1.5-flash')  # OpenRouter uses this format
                logger.info(f"CLI: OpenRouter model from env: {os.getenv('OPENROUTER_MODEL')}, using: {model_name}")
                logger.info(f"CLI: All MODEL env vars: OPENROUTER_MODEL={os.getenv('OPENROUTER_MODEL')}, REQUESTY_MODEL={os.getenv('REQUESTY_MODEL')}, DEFAULT_MODEL={os.getenv('DEFAULT_MODEL')}")
            elif selected_provider == 'requesty':
                model_name = os.getenv('REQUESTY_MODEL', 'coding/gemini-2.5-flash')  # Requesty uses this format
            # else:  # gemini - commented out
            #     model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
            else:
                # Fallback for any other provider
                model_name = os.getenv('DEFAULT_MODEL', 'coding/gemini-2.5-flash')

            logger.info("Using model", extra={"provider": selected_provider, "model": model_name})

            # Create GenerationRecord and save to DB
            record = GenerationRecord(
                id=generation_id,
                prompt=prompt,
                width=width or 512,
                height=height or 512,
                output_path=out_path,
                model=model_name,
                status="processing",
                created_at=datetime.now(),
                sha256=input_sha
            )
            db.save_generation(record)

            logger.info("Calling Gemini API", extra={"generation_id": generation_id, "template_path": actual_template_path, "params": params_dict, "provider": selected_provider, "model": model_name})
            generated_path, metadata = await call_gemini(actual_template_path, prompt, model=model_name, params=params_dict, provider=selected_provider)

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
                    "provider": selected_provider,
                    "out_path": out_path,
                    "created_at": datetime.now().isoformat(),
                    "sha256": metadata["sha256"],
                    "input_sha256": input_sha
                }))
            else:
                click.echo(f"Generated image using {selected_provider} saved to {out_path}")

            logger.info("Generation completed successfully", extra={
                "generation_id": generation_id,
                "provider": selected_provider,
                "out_path": out_path,
                "sha256": metadata["sha256"],
                "input_sha256": input_sha
            })
        except Exception as e:
            logger.error("Generation failed", extra={
                "generation_id": generation_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "template_path": actual_template_path if 'actual_template_path' in locals() else template_path,
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

        from .db import Database, APIProviderRecord, APIKeyRecord

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

@main.command()
@click.option('--provider', help='Specific provider to configure (skips interactive choice)')
@click.option('--non-interactive', is_flag=True, help='Skip interactive prompts, require --api-key')
@click.option('--api-key', help='API key value (required with --non-interactive)')
@click.option('--update-only', is_flag=True, help='Only allow updating existing providers')
def configure(provider, non_interactive, api_key, update_only):
    """Configure API provider settings with interactive prompts"""
    try:
        logger.info("Starting provider configuration", extra={
            "provider": provider,
            "non_interactive": non_interactive,
            "has_api_key": bool(api_key),
            "update_only": update_only
        })

        db = Database("bananagen.db")

        # Check for encryption function
        has_encryption = callable(encrypt_key)

        existing_provider = None

        # Handle non-interactive mode
        if non_interactive:
            if not provider:
                raise click.BadParameter("--provider is required in non-interactive mode")
            if not api_key:
                raise click.BadParameter("--api-key is required in non-interactive mode")

            # Get or create provider record
            existing_provider = db.get_api_provider(provider)
            if not existing_provider and update_only:
                raise click.BadParameter(f"Provider '{provider}' not found. Use --update-only=False to create new providers.")

        # Interactive configuration flow
        elif not provider:
            try:
                if update_only:
                    # Only allow updating existing providers
                    provider_name = list_existing_providers(db)
                    if not provider_name:
                        click.echo("No providers available to update.")
                        return
                else:
                    # Ask user what they want to do
                    choice = get_provider_choice()

                    if choice == '1':  # Configure new provider
                        existing_provider = None
                    else:  # Update existing provider
                        provider_name = list_existing_providers(db)
                        if provider_name:
                            existing_provider = db.get_api_provider(provider_name)
                        else:
                            click.echo("No existing providers found.")
                            return
            except Exception as e:
                logger.error("Error during provider selection", extra={"error": str(e)})
                raise click.ClickException(f"Error selecting provider: {e}")
        else:
            # Provider specified via --provider option
            try:
                existing_provider = db.get_api_provider(provider)
            except Exception as e:
                logger.error("Error retrieving provider", extra={"provider": provider, "error": str(e)})
                raise click.ClickException(f"Error retrieving provider '{provider}': {e}")

        # Get provider configuration details
        if non_interactive and existing_provider:
            # Non-interactive mode with existing provider - use current details
            provider_details = {
                'name': existing_provider.name,
                'display_name': existing_provider.display_name,
                'endpoint_url': existing_provider.endpoint_url,
                'model_name': existing_provider.model_name or "",
                'base_url': existing_provider.base_url or existing_provider.endpoint_url,
                'auth_type': existing_provider.auth_type
            }
        elif non_interactive and not existing_provider and provider:
            # Non-interactive mode creating new provider from command line
            # Validate the provided provider name first
            if not re.match(r'^[a-z0-9_-]+$', provider):
                raise click.BadParameter("Provider name can only contain lowercase letters, numbers, hyphens, and underscores")

            provider_details = {
                'name': provider,
                'display_name': provider.title(),
                'endpoint_url': f'https://api.{provider}.com/v1',  # Default endpoint
                'model_name': f'{provider}-default-model',  # Default model
                'base_url': f'https://api.{provider}.com/v1',  # Default base URL
                'auth_type': 'bearer'
            }
        else:
            # Interactive mode
            provider_details = prompt_provider_details(existing_provider)

        # Handle API key
        if non_interactive:
            if not api_key:
                raise click.BadParameter("API key is required in non-interactive mode")
            final_api_key = api_key
        else:
            final_api_key = prompt_api_key()

        # Confirmation (skip in non-interactive mode)
        if not non_interactive:
            if not confirm_configuration(provider_details):
                click.echo("Configuration cancelled.")
                return

        # Save provider configuration
        try:
            provider_record = existing_provider or APIProviderRecord(
                id=f"prov_{provider_details['name']}_{str(uuid.uuid4())[:8]}",
                name=provider_details['name'],
                display_name=provider_details['display_name'],
                endpoint_url=provider_details['endpoint_url'],
                auth_type=provider_details['auth_type'],
                model_name=provider_details['model_name'],
                base_url=provider_details['base_url'],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            # Update timestamps if updating existing provider
            if existing_provider:
                provider_record.updated_at = datetime.now()
                provider_record.settings = existing_provider.settings

            db.save_api_provider(provider_record)
            action = "Updated" if existing_provider else "Created"
            logger.info(f"{action.lower()} provider record", extra={
                "provider": provider_details['name'],
                "id": provider_record.id,
                "action": action.lower()
            })
        except Exception as e:
            logger.error("Failed to save provider to database", extra={
                "provider": provider_details['name'],
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise click.ClickException(f"Failed to save provider configuration to database: {e}")

        # Encrypt and save API key
        if has_encryption:
            encrypted_key = encrypt_key(final_api_key)
        else:
            encrypted_key = final_api_key
            logger.warning("API key encryption not available, storing in plaintext")

        # Check if API key already exists for this provider
        existing_keys = db.get_api_keys_for_provider(provider_record.id)
        if existing_keys:
            # Update existing key
            key_record = existing_keys[0]
            key_record.key_value = encrypted_key
            key_record.updated_at = datetime.now()
        else:
            # Create new key
            key_record = APIKeyRecord(
                id=f"key_{str(uuid.uuid4())}",
                provider_id=provider_record.id,
                key_value=encrypted_key,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

        db.save_api_key(key_record)
        logger.info("API key configured", extra={
            "provider": provider_details['name'],
            "key_id": key_record.id,
            "has_encryption": has_encryption
        })

        click.echo(f"✓ Provider '{provider_details['display_name']}' configured successfully!")
        if not has_encryption:
            click.echo("⚠ Warning: API key was stored without encryption. Please ensure your database is secure.")

    except Exception as e:
        logger.error("Configuration failed", extra={
            "error": str(e),
            "error_type": type(e).__name__,
            "provider": provider
        })
        click.echo(f"❌ Error: {e}", err=True)
        raise click.ClickException(f"Failed to configure provider: {e}")


# Interactive configuration functions are now integrated into the configure command


if __name__ == '__main__':
    main()
