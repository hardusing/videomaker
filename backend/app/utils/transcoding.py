import os
import ffmpeg
from pathlib import Path
import time


def get_video_info(file_path):
    """Get video information"""
    try:
        probe = ffmpeg.probe(file_path)
        video_info = next(s for s in probe["streams"] if s["codec_type"] == "video")
        return {
            "width": int(video_info["width"]),
            "height": int(video_info["height"]),
            "duration": float(probe["format"]["duration"]),
        }
    except ffmpeg.Error as e:
        print(f"Failed to get video info: {e.stderr.decode()}")
        return None


def encode_video(input_path, output_path):
    """Encode a single video file"""
    try:
        stream = (
            ffmpeg.input(input_path)
            .output(
                output_path,
                vcodec="libx264",  # Explicitly specify video codec
                acodec="aac",  # Explicitly specify audio codec
                **{
                    "profile:v": "main",  # Video profile
                    "level:v": "4.0",  # Video level
                    "preset": "slow",  # Encoding preset
                    "crf": 23,  # Constant Rate Factor
                    "b:a": "128k",  # Audio bitrate
                    "movflags": "+faststart",  # Enable fast start
                },
            )
            .overwrite_output()
        )

        # Run encoding process
        stream.run(capture_stdout=True, capture_stderr=True)
        return True
    except ffmpeg.Error as e:
        print(f"Encoding error: {e.stderr.decode()}")
        return False


def create_directory(directory_path):
    """Create directory if it doesn't exist"""
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        print(f"Error creating directory: {e}")
        return False


def process_directory(input_directory, output_directory):
    """Process all MP4 files in the directory and its subdirectories"""
    input_dir = Path(input_directory)
    output_dir = Path(output_directory)

    # Ensure input directory exists
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Input directory does not exist or is not valid: {input_dir}")
        return

    # Get all MP4 files recursively
    mp4_files = list(input_dir.rglob("*.mp4"))
    total_files = len(mp4_files)

    if total_files == 0:
        print("No MP4 files found")
        return

    print(f"Found {total_files} MP4 files")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")

    # Process each file
    for index, input_file in enumerate(mp4_files, 1):
        # Calculate relative path from input directory
        relative_path = input_file.relative_to(input_dir)

        # Create corresponding output path
        output_file = output_dir / relative_path.parent / f"encoded_{input_file.name}"

        # Create output directory if it doesn't exist
        if not create_directory(output_file.parent):
            print(f"Failed to create output directory: {output_file.parent}")
            continue

        # Skip if output file already exists
        if output_file.exists():
            print(
                f"[{index}/{total_files}] File already exists, skipping: {output_file.name}"
            )
            continue

        print(f"\n[{index}/{total_files}] Processing: {input_file}")

        # Get video information
        info = get_video_info(str(input_file))
        if info:
            print(
                f"Video info: {info['width']}x{info['height']}, Duration: {info['duration']:.2f} seconds"
            )

        # Record start time
        start_time = time.time()

        # Execute encoding
        if encode_video(str(input_file), str(output_file)):
            duration = time.time() - start_time
            print(f"Encoding completed: {output_file}")
            print(f"Time taken: {duration:.2f} seconds")
        else:
            print(f"Encoding failed: {input_file}")


if __name__ == "__main__":
    # Get current directory
    current_directory = "./raw_videos/"
    output_directory = "./outputs"

    # Start processing
    process_directory(current_directory, output_directory)