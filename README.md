# Lecture AI

A Streamlit web app for turning lecture recordings into transcripts and summaries. Students sign in, upload an audio or video recording straight from the browser to their own Google Drive, and track their recent lectures from a themed dashboard.

> **Status:** Sign-in, uploading and lecture history are fully working. The transcription and summary step is still a placeholder: the Results screen shows sample text, not real output from your recording.

## Features

- **Accounts:** email and password sign-up, sign-in, "Remember me" (30-day cookie), email confirmation and one-time-code password reset, all through Supabase Auth.
- **Direct-to-Drive uploads:** files go from the browser to Google Drive in 8 MB chunks, with up to 3 retries per chunk. Files never pass through the Streamlit server.
- **Large files:** up to 1 GB per recording.
- **Supported formats:** MP3, WAV, M4A, MP4, MKV, WEBM, OGG, MPEG, AVI, MOV, M4V, MPG, 3GP, FLAC, AAC, OPUS.
- **Lecture history:** the five most recent uploads are loaded from the database, so they persist across refreshes, logouts and devices.
- **Dashboard:** current lecture, pipeline progress ring, study tips and account card.
- **Light and dark themes:** the custom upload component follows the app's theme.
- **Times in IST:** all displayed times use Asia/Kolkata.

## How it works

```
Browser ──► Streamlit app (Test.py)
   │             │
   │             ├── Supabase Auth (sign-in, session token)
   │             └── Supabase DB (lecture_uploads history)
   │
   └─► Custom upload component (Vite + JS)
          1. start-upload    ─► Supabase Edge Function ─► Google Drive resumable session
          2. PUT chunks      ─► Google Drive (direct)
          3. complete-upload ─► Supabase Edge Function (verifies and records the file)
```

The Streamlit app passes the user's access token and the edge function URL to the upload component. The component then runs the three steps above.

## Project structure

```
Lecture-Summ/
├── Test.py                 # Streamlit app (auth, dashboard, routing)
├── requirements.txt        # Python dependencies
├── .gitignore
└── drive_uploader/         # Custom Streamlit component (Vite)
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── public/
    ├── src/
    │   ├── main.js         # Upload logic and theme bridge
    │   └── style.css
    └── build/              # Built output that Streamlit actually serves (commit this)
        ├── index.html
        └── assets/
```

## Requirements

- Python 3.9 or newer
- Node.js 18 or newer (only to rebuild the upload component)
- A Supabase project with:
  - Auth enabled
  - A `lecture_uploads` table with `file_name`, `size_bytes`, `status` and `created_at` columns
  - An edge function named `google-drive-upload` that handles the actions `start-upload`, `complete-upload` and `prepare-upload`
- A Google Cloud project with the Drive API enabled, used by the edge function

## Setup

### 1. Clone and install

```bash
git clone https://github.com/<your-username>/Lecture-Summ.git
cd Lecture-Summ
pip install -r requirements.txt
```

`requirements.txt` should contain at least:

```
streamlit
supabase
streamlit-cookies-controller
requests
```

### 2. Add your secrets

For local development, create a `.env` file next to `Test.py`:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-publishable-anon-key
APP_URL=http://localhost:8501
```

`APP_URL` is optional. It is where confirmation emails send people.

On Streamlit Cloud, add the same values under **App settings → Secrets**:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-publishable-anon-key"
APP_URL = "https://your-app.streamlit.app"
```

Use only the **publishable (anon) key**. Never put the service-role key in this project.

### 3. Run it

```bash
streamlit run Test.py
```

## Rebuilding the upload component

Streamlit serves the *built* component, so rebuild after any change to `main.js` or `style.css`:

```bash
cd drive_uploader
npm install
npm run build
```

Then commit the updated `drive_uploader/build/` folder. Streamlit Cloud does not run `npm build` for you.

Make sure `vite.config.js` sets `base: './'` and `build.outDir` to `'build'`, otherwise the component loads blank inside Streamlit.

## Deploying to Streamlit Cloud

1. Push the repo to GitHub, including `drive_uploader/build/`.
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app.
3. Choose the repo, branch `main`, and set the main file path to `Test.py`.
4. Add your secrets under **Advanced settings → Secrets**.
5. Deploy. After later pushes, reboot the app from **Manage app**.

## Troubleshooting

| Problem | Likely cause |
| --- | --- |
| Upload box is blank | `base: './'` missing in `vite.config.js`, or `build/` was not committed |
| "Supabase credentials are missing" | `SUPABASE_URL` or `SUPABASE_KEY` not set in `.env` or Secrets |
| "Your login session has expired" | The access token expired. Sign out and sign in again |
| Upload fails at the last chunk | Google Drive blocked the response (CORS or network). Check the edge function's allowed origins |
| Times look 5.5 hours off | An old copy of `Test.py` without the IST conversion is deployed |
| Changes to the upload box don't appear | `npm run build` was not re-run, or the new `build/` was not pushed |

## Tech stack

Streamlit, Supabase (Auth, Postgres, Edge Functions), Google Drive API, Vite, `streamlit-component-lib`.

## Roadmap

- Real audio extraction and speech-to-text
- AI-generated summaries and key points
- Saved results per lecture
- Showing past lectures' results from history

## License

Add your preferred license here (for example MIT).
