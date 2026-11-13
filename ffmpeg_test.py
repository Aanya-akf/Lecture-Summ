import streamlit as st
import shutil
import subprocess
import tempfile
import os
from audio_processor import transcribe_audio

st.set_page_config(page_title="FFmpeg Test")

st.title("FFmpeg Installation Test")

st.write("Checking whether FFmpeg is installed on the server...")

ffmpeg_path = shutil.which("ffmpeg")

if ffmpeg_path:
    st.success("FFmpeg is installed!")

    result = subprocess.run(
        [ffmpeg_path, "-version"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        st.write("Installed FFmpeg version:")
        st.code(result.stdout.splitlines()[0])
    else:
        st.error("FFmpeg was found, but could not run.")

else:
    st.error("FFmpeg is not installed.")

st.divider()

st.subheader("Audio Conversion Test")

uploaded_file = st.file_uploader(
    "Upload an audio file",
    type=["mp3", "m4a", "wav", "aac", "ogg", "flac"]
)

if uploaded_file:
    st.success(f"Uploaded: {uploaded_file.name}")
    st.write("File size:", round(uploaded_file.size / (1024 * 1024), 2), "MB")

if uploaded_file and ffmpeg_path:
    if st.button("Convert to WAV"):

        with tempfile.TemporaryDirectory() as temp_dir:

            input_path = os.path.join(temp_dir, uploaded_file.name)
            output_path = os.path.join(temp_dir, "converted_audio.wav")

            with open(input_path, "wb") as file:
                file.write(uploaded_file.getbuffer())

            command = [
                ffmpeg_path,
                "-i", input_path,
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                "-y",
                output_path
            ]

            try:
                subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True
                )

                st.success("Audio converted successfully!")

                with open(output_path, "rb") as file:
                    st.download_button(
                        "Download converted WAV",
                        data=file,
                        file_name="converted_audio.wav",
                        mime="audio/wav"
                    )

            except subprocess.CalledProcessError as error:
                st.error("Audio conversion failed.")
                st.code(error.stderr)

st.divider()
st.subheader("Whisper Installation Test")

try:
    import whisper
    st.success("Whisper is installed and imported successfully!")

except Exception as error:
    st.error("Whisper import failed.")
    st.exception(error)

st.divider()
st.subheader("Whisper Model Test")

if st.button("Load Whisper Tiny Model"):

    with st.spinner("Loading Whisper model..."):
        try:
            model = whisper.load_model("tiny")

            st.success("Whisper tiny model loaded successfully!")

        except Exception as error:
            st.error("Whisper model loading failed.")
            st.exception(error)

st.divider()
st.subheader("Whisper Transcription Test")

if uploaded_file and ffmpeg_path:

    if st.button("Transcribe Audio"):

        with st.spinner("Converting and transcribing audio..."):

            try:
                with tempfile.TemporaryDirectory() as temp_dir:

                    input_path = os.path.join(
                        temp_dir, uploaded_file.name
                    )

                    output_path = os.path.join(
                        temp_dir, "converted_audio.wav"
                    )

                    with open(input_path, "wb") as file:
                        file.write(uploaded_file.getbuffer())

                    command = [
                        ffmpeg_path,
                        "-i", input_path,
                        "-vn",
                        "-ac", "1",
                        "-ar", "16000",
                        "-y",
                        output_path
                    ]

                    subprocess.run(
                        command,
                        check=True,
                        capture_output=True,
                        text=True
                    )

                    model = whisper.load_model("tiny")

                    transcript = transcribe_audio(output_path, model)

                    st.success("Transcription completed!")
                    st.text_area(
                        "Generated Transcript",
                        transcript,
                        height=250
                    )

            except Exception as error:
                st.error("Transcription failed.")
                st.exception(error)