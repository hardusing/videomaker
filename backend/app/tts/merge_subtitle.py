import re


def parse_time(time_str):
    """Parse SRT timestamp to milliseconds"""
    hours, minutes, seconds = time_str.split(":")
    seconds, milliseconds = seconds.split(",")
    return (
        int(hours) * 3600000
        + int(minutes) * 60000
        + int(seconds) * 1000
        + int(milliseconds)
    )


def format_time(milliseconds):
    """Format milliseconds to SRT timestamp"""
    hours = milliseconds // 3600000
    minutes = (milliseconds % 3600000) // 60000
    seconds = (milliseconds % 60000) // 1000
    millisecs = milliseconds % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millisecs:03d}"


def merge_subtitles(input_file, output_file, max_duration=5000, max_chars=40):
    """
    Merge short subtitles into longer ones
    Args:
        input_file: Input SRT file path
        output_file: Output SRT file path
        max_duration: Maximum duration for merged subtitle (milliseconds)
        max_chars: Maximum characters per subtitle
    """
    # Read input file
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # Split into subtitle blocks
    subtitle_blocks = re.split(r"\n\n+", content)

    # Parse subtitles
    subtitles = []
    for block in subtitle_blocks:
        lines = block.split("\n")
        if len(lines) >= 3:  # Valid subtitle block
            times = lines[1].split(" --> ")
            subtitles.append(
                {
                    "start": parse_time(times[0]),
                    "end": parse_time(times[1]),
                    "text": " ".join(lines[2:]),
                }
            )

    # Merge subtitles
    merged = []
    current = None

    for sub in subtitles:
        if current is None:
            current = sub.copy()
            continue

        # Check if we should merge
        gap = sub["start"] - current["end"]
        merged_duration = sub["end"] - current["start"]
        merged_text = current["text"] + sub["text"]

        if (
            gap < 300  # Less than 300ms gap
            and merged_duration <= max_duration  # Not too long
            and len(merged_text) <= max_chars  # Not too many characters
            and not any(
                current["text"].endswith(x) for x in ["。", "！", "？", ".", "!", "?"]
            )
        ):  # Not end of sentence

            current["end"] = sub["end"]
            current["text"] = merged_text
        else:
            merged.append(current)
            current = sub.copy()

    if current:
        merged.append(current)

    # Write output file
    with open(output_file, "w", encoding="utf-8") as f:
        for i, sub in enumerate(merged, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time(sub['start'])} --> {format_time(sub['end'])}\n")
            f.write(f"{sub['text']}\n\n")
