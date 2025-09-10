import click
from .core import generate_placeholder
from .gemini_adapter import call_gemini

@click.group()
def main():
    """Bananagen CLI"""
    pass

@main.command()
@click.option('--width', type=int, required=True, help='Image width')
@click.option('--height', type=int, required=True, help='Image height')
@click.option('--color', default='#ffffff', help='Background color')
@click.option('--transparent', is_flag=True, help='Make background transparent')
@click.option('--out', 'out_path', required=True, help='Output file path')
def placeholder(width, height, color, transparent, out_path):
    """Generate placeholder images"""
    generate_placeholder(width, height, color, transparent, out_path)
    click.echo(f"Placeholder saved to {out_path}")

@main.command()
@click.option('--placeholder', 'template_path', help='Placeholder image path')
@click.option('--prompt', required=True, help='Generation prompt')
@click.option('--width', type=int, help='Image width (if no placeholder)')
@click.option('--height', type=int, help='Image height (if no placeholder)')
@click.option('--out', 'out_path', required=True, help='Output file path')
@click.option('--json', is_flag=True, help='Output JSON')
def generate(template_path, prompt, width, height, out_path, json):
    """Generate images using Gemini"""
    if not template_path:
        # Generate placeholder first
        template_path = out_path.replace(".png", "_placeholder.png")
        generate_placeholder(width or 512, height or 512, out_path=template_path)
    
    generated_path, metadata = call_gemini(template_path, prompt)
    
    # For now, just copy to out_path
    import shutil
    shutil.copy(generated_path, out_path)
    
    if json:
        import json
        click.echo(json.dumps({"id": "mock-uuid", "status": "done", "out_path": out_path, "sha256": metadata["sha256"]}))
    else:
        click.echo(f"Generated image saved to {out_path}")

# Add other subcommands as placeholders
@main.command()
def batch():
    """Batch processing"""
    click.echo("Batch command - not implemented yet")

@main.command()
def scan():
    """Scan and replace"""
    click.echo("Scan command - not implemented yet")

@main.command()
def serve():
    """Serve API"""
    click.echo("Serve command - not implemented yet")

@main.command()
@click.argument('id')
def status(id):
    """Check status"""
    click.echo(f"Status for {id} - not implemented yet")

if __name__ == '__main__':
    main()
