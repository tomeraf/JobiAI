"""
Create a simple icon for JobiAI.

This script generates a simple icon file that can be used for the desktop app.
Run this script to generate icon.ico and icon.png files.

Requirements: pip install Pillow
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size: int = 256, color: str = '#4A90D9') -> Image.Image:
    """Create a simple JobiAI icon (blue circle with J)."""
    # Create image with transparency
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw circle background
    margin = size // 16
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color
    )

    # Draw "J" letter
    # Try to use a nice font, fall back to default
    font_size = size // 2
    try:
        # Try to use Arial or similar
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

    text = "J"

    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (size - text_width) // 2
    y = (size - text_height) // 2 - size // 16  # Slight adjustment for visual centering

    draw.text((x, y), text, fill='white', font=font)

    return image


def create_ico_file(image: Image.Image, output_path: str):
    """Save image as .ico file with multiple sizes."""
    # Create multiple sizes for the ICO
    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for s in sizes:
        resized = image.resize((s, s), Image.Resampling.LANCZOS)
        images.append(resized)

    # Save as ICO
    images[0].save(
        output_path,
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )


def main():
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("Creating JobiAI icons...")

    # Create the icon
    icon = create_icon(size=256, color='#4A90D9')

    # Save as PNG
    png_path = os.path.join(script_dir, 'icon.png')
    icon.save(png_path, format='PNG')
    print(f"Created: {png_path}")

    # Save as ICO
    ico_path = os.path.join(script_dir, 'icon.ico')
    create_ico_file(icon, ico_path)
    print(f"Created: {ico_path}")

    # Create a smaller version for tray
    tray_icon = create_icon(size=64, color='#4A90D9')
    tray_path = os.path.join(script_dir, 'icon_tray.png')
    tray_icon.save(tray_path, format='PNG')
    print(f"Created: {tray_path}")

    print("\nDone! Icons created in assets folder.")


if __name__ == '__main__':
    main()
