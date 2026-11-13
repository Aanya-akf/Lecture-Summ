import subprocess
import shutil
import os
import tempfile
import whisper
from pathlib import Path
def check_ffmpeg():
    """Find an FFmpeg installation that can actually run."""

    for folder in os.environ["PATH"].split(os.pathsep):
        filename = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        candidate = Path(folder) / filename

        if candidate.is_file():
            try:
                subprocess.run(
                    [str(candidate), "-version"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                return str(candidate)

            except (OSError, subprocess.CalledProcessError):
                continue

    raise RuntimeError("No working FFmpeg installation found.")
def check_ffprobe():
    """Find a working FFprobe installation."""

    for folder in os.environ["PATH"].split(os.pathsep):
        filename = "ffprobe.exe" if os.name == "nt" else "ffprobe"
        candidate = Path(folder) / filename

        if candidate.is_file():
            try:
                subprocess.run(
                    [str(candidate), "-version"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                return str(candidate)

            except (OSError, subprocess.CalledProcessError):
                continue

    raise RuntimeError("No working FFprobe installation found.")
def get_audio_info(input_file):
    """Extract basic information about an audio file."""

    ffprobe = check_ffprobe()

    command = [
        ffprobe,
        "-v", "error",
        "-show_entries",
        "format=duration,size,format_name:stream=sample_rate,channels",
        "-of", "json",
        str(input_file)
    ]

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True
    )

    import json
    data = json.loads(result.stdout)

    audio_stream = next(
        (s for s in data.get("streams", []) if "sample_rate" in s),
        {}
    )

    return {
        "duration_seconds": float(data["format"]["duration"]),
        "size_mb": round(int(data["format"]["size"]) / (1024 * 1024), 2),
        "format": data["format"]["format_name"],
        "sample_rate": audio_stream.get("sample_rate"),
        "channels": audio_stream.get("channels")
    }
def convert_to_wav(input_file, output_file):
    """Convert an audio or video file into WAV format."""

    ffmpeg = check_ffmpeg()

    command = [
        ffmpeg,
        "-i", str(input_file),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-y",
        str(output_file)
    ]

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True
    )

    return output_file

def transcribe_audio(input_file, model):
    """
    Transcribe an audio file using a loaded Whisper model.
    """

    result = model.transcribe(str(input_file))

    transcript = result["text"].strip()

    return transcript

if __name__ == "__main__":
    input_file = r"C:\Users\LENOVO\Downloads\06-11-2026 23.07.m4a"
    output_file = "converted_audio.wav"

    try:
        print("FFprobe found at:", check_ffprobe())
        info = get_audio_info(input_file)

        print("Original audio information:")
        print(info)

        result = convert_to_wav(input_file, output_file)
        print("Conversion successful!")
        print("WAV file saved at:", result)
        wav_info = get_audio_info(output_file)

        print("Converted WAV information:")
        print(wav_info)
    except Exception as error:
        print("Error:", error)

