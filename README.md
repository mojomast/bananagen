# Bananagen

A CLI tool that produces ready-to-use image assets by driving the Nano Banana (Gemini 2.5 Flash) model.

## Installation

```bash
pip install bananagen
# or
poetry install
```

## Usage

### Generate a placeholder
```bash
bananagen placeholder --width 1024 --height 768 --out placeholder.png
```

### Generate an image
```bash
bananagen generate --placeholder placeholder.png --prompt "A cozy cabin in snow" --out cabin.png
```

### Batch processing
```bash
bananagen batch --list jobs.json --concurrency 3
```

### Scan and replace
```bash
bananagen scan --root ./site --pattern "*__placeholder__*" --replace
```

### Serve API
```bash
bananagen serve --port 9090
```

## For Coding Agents

Use `--json` for machine-readable output:

```bash
bananagen generate --prompt "A banana" --width 512 --height 512 --out banana.png --json
# {"id": "uuid", "status": "queued", "out_path": "banana.png", "created_at": "2025-09-10T12:00:00Z"}
```

Poll status:
```bash
bananagen status <id>
# or API: GET /status/<id>
```
