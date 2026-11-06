# Lecture AI

Lecture AI is a web app that helps students turn lecture recordings into
transcripts and summaries.

You sign in, upload a recording of your lecture, and the app keeps track of
everything on a simple dashboard. Your files are saved to your own Google Drive,
so they stay private.

> **Current status:** Sign-in, uploading and the dashboard all work.
> Automatic transcripts and summaries are still being built, so the Results
> page shows sample text for now.

## Who is it for?

- Students who record their classes and want them organised in one place
- Anyone who wants notes from long lectures without re-watching them
- Study groups who want a simple way to keep their recordings safe

## What you can do

- **Create an account** and sign in with your email and password
- **Stay signed in** on your device if you choose "Remember me"
- **Reset your password** by email if you forget it
- **Upload lecture recordings** (audio or video) of up to 1 GB
- **See your recent lectures** on the dashboard, even after you log out
- **Switch between light and dark mode**

## Supported file types

| Type  | Formats                                       |
| ----- | --------------------------------------------- |
| Audio | MP3, WAV, M4A, OGG, FLAC, AAC, OPUS           |
| Video | MP4, MKV, WEBM, MOV, AVI, MPEG, MPG, M4V, 3GP |

## How it works

Here is the journey of a lecture, in plain steps:

1. **You sign in.** The app checks who you are.
2. **You pick a recording.** The app checks that it is a supported type and
   not bigger than 1 GB.
3. **The upload starts.** Your file is sent in small pieces straight from your
   browser to your Google Drive. If a piece fails, the app tries again.
4. **The upload is confirmed.** The app checks that the whole file arrived.
5. **It shows up on your dashboard** under "Recent lectures".

Because the file goes directly to Google Drive, the app itself never has to
store or handle your recording.

## What is inside this project

```
Lecture-Summ/
├── Test.py              The main app (screens, sign-in, dashboard)
├── requirements.txt     Python packages the app needs
└── drive_uploader/      The upload box shown on the page
    ├── src/             The upload box's code and styling
    ├── public/          Small images and icons
    └── build/           The ready-to-use version of the upload box
```

- **`Test.py`** draws every screen, handles signing in and out, and shows
  your recent lectures.
- **`drive_uploader/`** makes the upload box. It is written in JavaScript and
  "built" into the `build/` folder, which is the part the app actually uses.

## Built with

- **Streamlit** for the web pages, written in Python
- **Vite and JavaScript** for the upload box
- **Supabase** for accounts and your lecture list
- **Google Drive** for storing your recordings

## Running it on your computer

You need Python 3.9 or newer. Node.js is only needed if you change the
upload box.

```bash
git clone https://github.com/<your-username>/Lecture-Summ.git
cd Lecture-Summ
pip install -r requirements.txt
streamlit run Test.py
```

Then open the link shown in your terminal (usually `http://localhost:8501`).
You also need your own Supabase project and Google Drive access set up for
everything to work.

## Changing the upload box

The app uses the built version, so after editing anything in
`drive_uploader/src/`, rebuild it and upload the new `build/` folder:

```bash
cd drive_uploader
npm install
npm run build
```

## Putting it online

1. Upload the project to GitHub, including the `build/` folder.
2. Go to [share.streamlit.io](https://share.streamlit.io) and make a new app.
3. Pick this project, choose the `main` branch, and set the main file to
   `Test.py`.
4. Press **Deploy**.

After pushing changes later, restart the app from the **Manage app** menu.

## Common problems

| Problem                    | What to try                                  |
| -------------------------- | -------------------------------------------- |
| The upload box is blank    | Run `npm run build` and upload `build/` again |
| It says my session expired | Log out and sign in again                    |
| The time looks wrong       | Make sure you have the latest `Test.py`      |
| Changes do not show up     | Restart the app and refresh the page         |
| A big upload fails         | Check your internet and try again            |

## Coming soon

- Turning speech into text (transcripts)
- Short summaries and key points
- Saved results for every lecture

## License

To be added.
