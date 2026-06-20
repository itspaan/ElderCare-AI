# Deployment Guide — ElderCare AI (Render / Railway)

How to host ElderCare AI on a free cloud platform so survey participants can open
a public `https://` link. The steps below use **Render**; Railway is nearly
identical (the same start command and environment variables apply).

> Goal: a public URL like `https://eldercare-ai.onrender.com` that runs your
> existing FastAPI app.

---

## 1. Before you start — two things that will bite you

The repo's `.gitignore` excludes two things the running app needs:

1. **`*.pkl` — the trained model is NOT in git.** The container has no model
   unless you either (a) train it during build, or (b) un-ignore the file.
   This guide trains it at build time (recommended — reproducible).
2. **`storage/` is gitignored *and* the free-tier filesystem is EPHEMERAL.**
   Anything written to disk (SQLite reminders, uploaded images, **and any survey
   data**) is **wiped on every redeploy/restart**. This is fine for a demo, but
   **not safe for collecting survey data.** See §6 and
   [DATA_COLLECTION.md](DATA_COLLECTION.md) for how to persist real data.

---

## 2. Prerequisites

- A GitHub repo containing this project (push your code first).
- A free [Render](https://render.com) account (sign in with GitHub).
- Your `GEMINI_API_KEY`.

---

## 3. Files to add to the repo

### 3.1 Pin dependencies (recommended)
`requirements.txt` is currently unpinned. Unpinned installs can break later when
a library releases a new major version. Pin the versions you tested with, e.g.:

```
fastapi==0.115.*
uvicorn==0.34.*
google-genai==1.*
python-dotenv==1.*
scikit-learn==1.5.*
pandas==2.*
numpy==2.*
```
> Run `pip freeze` in your working venv to get the exact versions you use, then
> copy the relevant lines.

### 3.2 Pin the Python version
Add a file named `runtime.txt` in the project root so the host matches your local
Python:

```
python-3.13.4
```

### 3.3 (Optional) a render.yaml for one-click config
You can configure everything in the dashboard instead, but a `render.yaml` makes
it reproducible:

```yaml
services:
  - type: web
    name: eldercare-ai
    runtime: python
    buildCommand: "pip install -r requirements.txt && python -m data.generate_dummy && python -m training.train_model"
    startCommand: "uvicorn main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: GEMINI_API_KEY
        sync: false   # set the value in the dashboard, never commit it
```

---

## 4. Create the service on Render

1. **New → Web Service**, connect your GitHub repo.
2. **Build Command:**
   ```
   pip install -r requirements.txt && python -m data.generate_dummy && python -m training.train_model
   ```
   (This regenerates the dataset and trains the `.pkl` inside the container, so
   the missing-model problem from §1 is solved.)
3. **Start Command:**
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
   > `$PORT` is provided by Render. Do **not** hardcode 8000 in production.
4. **Environment → Add Environment Variable:**
   - Key: `GEMINI_API_KEY`  Value: *(your key)*
5. **Instance type:** Free is fine for a survey (note: free instances **sleep**
   after inactivity and take ~30–60s to wake on the first request).
6. Click **Create Web Service** and watch the build logs.

---

## 5. Verify it works

Once deployed, check the health endpoint in a browser or with curl:

```
GET https://<your-app>.onrender.com/api/health
→ {"status":"active","model_loaded":true}
```

- `model_loaded: true` confirms the build trained the model correctly.
- Open `https://<your-app>.onrender.com/` for the UI.
- Open `https://<your-app>.onrender.com/docs` for the auto-generated API docs.

---

## 6. ⚠️ Persisting data (required before a real survey)

On the free tier the disk is ephemeral, so `storage/` is **not** durable. Options,
cheapest first:

| Option | Persistence | Notes |
|---|---|---|
| **External managed Postgres** (e.g. Render Postgres free, or Supabase free) | ✅ Durable | Best for survey data. Store responses in a table instead of SQLite/JSON. |
| **Render Persistent Disk** | ✅ Durable | Paid add-on; lets you keep the current SQLite/file approach by mounting a disk at `storage/`. |
| **Stay on ephemeral disk** | ❌ Lost on restart | OK for demos only. **Do not** collect real survey data this way. |

For the thesis survey, plan to write responses to an external database. The
schema and flow are described in [DATA_COLLECTION.md](DATA_COLLECTION.md).

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `model_loaded: false` | Build didn't train the model | Confirm the build command includes the training steps (§4.2) |
| 500 on `/api/chat` | Missing/invalid `GEMINI_API_KEY` | Set it in Environment; redeploy |
| First request very slow | Free instance was asleep | Expected; it wakes in ~30–60s |
| Reminders/images vanish | Ephemeral disk | Use a persistent store (§6) |
| Build fails on a package | Unpinned dependency changed | Pin versions (§3.1) |

---

## 8. Local "production-like" run (to test before deploying)

```powershell
.\venv\Scripts\Activate.ps1
uvicorn main:app --host 0.0.0.0 --port 8000
```
Then open `http://<your-PC-LAN-IP>:8000` from another device on the same Wi-Fi to
simulate a remote participant.
