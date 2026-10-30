# JEE Prep Tracker

A tiny, local, single-user web app to track JEE Main (January + April 2027) and
Class 12 Boards preparation. Built from `JEE_Boards_Preparation_Tracker.xlsx`.

No external services, no accounts, no internet dependency after setup — just a
SQLite file (`jee_tracker.db`) that lives next to the app and is created
automatically on first run.

## Features

- **Dashboard** — current score, January/April targets with live day countdowns,
  topic-completion metrics, and an editable settings panel.
- **Topic Tracker** — all 78 chapters (Class 11 + 12 Physics/Chemistry/Maths)
  with theory status, confidence, PYQ/sheet checkboxes, accuracy, notes, and an
  indicative completion % per topic. Filter by class/subject/priority/status.
- **Mock Tests** — log 30 mock attempts (score, subject split, accuracy,
  error pattern, next actions).
- **Milestones** — the original 9-phase study plan, with the current phase
  auto-highlighted based on today's date and your exam dates.
- **Reset** — reset topics, mock tests, milestones, settings, or everything,
  independently, at any time.

## Setup (uses a Python virtual environment)

```bash
cd "/home/himanshuraj/Learn/projects/JEE"
python3 -m venv .venv          # already created
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate
cd app
python app.py
```

Then open http://127.0.0.1:5000 in your browser. Stop with `Ctrl+C`.

## Data

Everything is stored in `jee_tracker.db` (SQLite) at the project root, created
automatically the first time you run the app. Delete this file (or use the
in-app "Reset entire tracker" button on the Dashboard) to start fresh.
