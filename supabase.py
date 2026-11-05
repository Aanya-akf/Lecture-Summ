import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

# Load credentials from .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

st.title("Supabase Connection Test")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Credentials not found. Check your .env file.")
    st.stop()

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    st.success("Supabase client initialized successfully!")
except Exception as e:
    st.error(f"Connection setup failed: {e}")
