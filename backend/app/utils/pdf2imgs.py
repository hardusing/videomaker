#!/usr/bin/env python3
import os
import argparse
from pathlib import Path
from PIL import Image
import numpy as np
import pdf2image  # Use pdf2image instead of PyMuPDF


def pdf_to_jpg(pdf_path, output_dir=None, max_size=768, dpi=300):
    """
    Convert PDF to JPG images, one per page, with the longest side at max_size pixels
    and the remaining space filled with black.

    Args:
        pdf_path (str): Path to the PDF file
        output_dir (str, optional): Directory to save the images. If None, uses the PDF's directory
        max_size (int): Maximum size of the longest dimension in pixels
        dpi (int): DPI for rendering PDF pages

    Returns:
        list: List of paths to the generated images (relative to current directory)
    """
    # Ensure input file exists
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Set up output directory
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(pdf_path), "jpg_output")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Get the base filename without extension
    base_filename = os.path.splitext(os.path.basename(pdf_path))[0]

    # Convert PDF to PIL Images using pdf2image
    images = pdf2image.convert_from_path(pdf_path, dpi=dpi)
    image_paths = []

    # Process each page
    for page_num, img in enumerate(images):

        # Calculate new dimensions while maintaining aspect ratio
        width, height = img.size
        aspect_ratio = width / height

        if width > height:
            # Width is the longest side
            new_width = max_size
            new_height = int(max_size / aspect_ratio)
        else:
            # Height is the longest side
            new_height = max_size
            new_width = int(max_size * aspect_ratio)

        # Resize the image
        img = img.resize((new_width, new_height), Image.LANCZOS)

        # Create a new black image with the largest dimension being max_size
        if width > height:
            # Width is the longest side
            black_img = Image.new("RGB", (max_size, max_size), color="black")
            # Paste the resized image onto the black canvas (centered)
            y_offset = (max_size - new_height) // 2
            black_img.paste(img, (0, y_offset))
        else:
            # Height is the longest side
            black_img = Image.new("RGB", (max_size, max_size), color="black")
            # Paste the resized image onto the black canvas (centered)
            x_offset = (max_size - new_width) // 2
            black_img.paste(img, (x_offset, 0))

        # Save the image
        output_filename = f"{base_filename}_page_{page_num+1:03d}.jpg"
        output_path = os.path.join(output_dir, output_filename)
        black_img.save(output_path, "JPEG", quality=95)

        # Add the relative path to our list
        rel_path = os.path.relpath(output_path)
        image_paths.append(rel_path)

    return image_paths


def main():
    parser = argparse.ArgumentParser(description="Convert PDF to JPG images")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF file")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save the images (default: creates jpg_output in same dir as PDF)",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=768,
        help="Maximum size of the longest dimension in pixels (default: 768)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="DPI for rendering PDF pages (default: 300)",
    )

    args = parser.parse_args()

    try:
        image_paths = pdf_to_jpg(
            args.pdf_path, args.output_dir, args.max_size, args.dpi
        )

        print(f"Successfully converted PDF to {len(image_paths)} JPG images:")
        for path in image_paths:
            print(f"  - {path}")

    except ModuleNotFoundError:
        print(
            "Error: pdf2image module not found. Please install it with: pip install pdf2image"
        )
        print("Note: pdf2image requires poppler to be installed:")
        print("  - On Ubuntu/Debian: sudo apt-get install poppler-utils")
        print("  - On macOS: brew install poppler")
        print(
            "  - On Windows: download and install from https://github.com/oschwartz10612/poppler-windows/releases/"
        )
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
