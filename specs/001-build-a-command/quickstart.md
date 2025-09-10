# Quickstart Guide

## Installation
```bash
pip install bananagen
# or
poetry add bananagen
```

Set environment variable:
```bash
export NANO_BANANA_API_KEY=your_key_here
```

## Basic Usage

### Generate a placeholder image
```bash
bananagen placeholder --width 1024 --height 768 --out placeholder.png
```

### Generate an image from placeholder
```bash
bananagen generate --placeholder placeholder.png --prompt "A cozy cabin in snow" --out cabin.png
```

### Batch processing
Create jobs.json:
```json
[
  {
    "prompt": "A banana",
    "width": 512,
    "height": 512,
    "out_path": "banana1.png"
  },
  {
    "prompt": "A bunch of bananas",
    "width": 512,
    "height": 512,
    "out_path": "banana2.png"
  }
]
```

Run batch:
```bash
bananagen batch --list jobs.json --concurrency 2
```

### Scan and replace
```bash
bananagen scan --root ./my-project --pattern "*placeholder*" --replace
```

### Serve API for agents
```bash
bananagen serve --port 9090
```

Then agents can POST to http://localhost:9090/generate

## Validation Scenarios

1. **Given** a prompt and dimensions, **When** running generate, **Then** an image is created matching the size.

2. **Given** a batch file, **When** running batch, **Then** all jobs are processed.

3. **Given** a repo with placeholders, **When** running scan, **Then** placeholders are replaced with generated images.

4. **Given** invalid prompt, **When** running generate, **Then** error is returned with clear message.

5. **Given** network failure, **When** running generate, **Then** retries with backoff.
