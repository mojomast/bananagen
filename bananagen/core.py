from PIL import Image

def generate_placeholder(width: int, height: int, color: str = "#ffffff", transparent: bool = False, out_path: str = None):
    """Generate a placeholder image."""
    if transparent:
        mode = "RGBA"
        color = (255, 255, 255, 0)  # transparent white
    else:
        mode = "RGB"
        # parse color
        if color.startswith("#"):
            color = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        else:
            color = (255, 255, 255)  # default white

    img = Image.new(mode, (width, height), color)
    if out_path:
        img.save(out_path)
    return img
