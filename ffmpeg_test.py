import streamlit as st
import shutil
import subprocess

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