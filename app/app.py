"""JEE + Boards Prep Tracker - a tiny Flask app backed by SQLite (or Turso/libSQL
when deployed, see database.py).

Run with:  python app.py
Then open http://127.0.0.1:5000
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Make sure this file's own directory is importable regardless of how/where
# it's loaded from (e.g. Vercel imports app/app.py in isolation and does not
# add its directory to sys.path, which would otherwise break `import database`).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, redirect, render_template, request, url_for

import database as db

app = Flask(__name__)
db.init_db()


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def days_between(today, target):
    if not target:
        return None
    return (target - today).days


@app.context_processor
def inject_today():
    return {"today": date.today()}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    settings = db.get_settings()
    metrics = db.get_dashboard_metrics()

    today = date.today()
    jan_exam = parse_date(settings.get("jan_exam_date"))
    april_exam = parse_date(settings.get("april_exam_date"))

    countdowns = {
        "jan_days_left": days_between(today, jan_exam),
        "april_days_left": days_between(today, april_exam),
    }

    return render_template(
        "dashboard.html",
        settings=settings,
        metrics=metrics,
        countdowns=countdowns,
    )


@app.route("/settings/update", methods=["POST"])
def settings_update():
    fields = [
        "current_score", "jan_target", "april_target",
        "current_score_date", "jan_exam_date", "april_exam_date",
    ]
    values = {f: request.form.get(f, "") for f in fields}
    db.update_settings(values)
    return redirect(url_for("dashboard"))


@app.route("/settings/reset", methods=["POST"])
def settings_reset():
    db.reset_settings()
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Topic tracker
# ---------------------------------------------------------------------------

STATUS_OPTIONS = ["Not started", "In progress", "Completed", "Revision needed"]
PRIORITY_OPTIONS = ["High", "Medium", "Low"]


@app.route("/topics")
def topics_list():
    class_filter = request.args.get("class_") or None
    subject_filter = request.args.get("subject") or None
    priority_filter = request.args.get("priority") or None
    status_filter = request.args.get("status") or None

    topics = db.get_all_topics(class_filter, subject_filter, priority_filter, status_filter)
    for t in topics:
        t["completion"] = db.compute_completion(t)

    return render_template(
        "topics.html",
        topics=topics,
        class_filter=class_filter,
        subject_filter=subject_filter,
        priority_filter=priority_filter,
        status_filter=status_filter,
        status_options=STATUS_OPTIONS,
        priority_options=PRIORITY_OPTIONS,
    )


@app.route("/topics/<int:topic_id>/edit")
def topic_edit(topic_id):
    topic = db.get_topic(topic_id)
    if not topic:
        return redirect(url_for("topics_list"))
    topic["completion"] = db.compute_completion(topic)
    return render_template(
        "topic_edit.html",
        topic=topic,
        status_options=STATUS_OPTIONS,
        priority_options=PRIORITY_OPTIONS,
    )


@app.route("/topics/<int:topic_id>/update", methods=["POST"])
def topic_update(topic_id):
    form = request.form
    fields = {
        "theory_status": form.get("theory_status", "Not started"),
        "concept_confidence": int(form.get("concept_confidence", 1)),
        "formula_confidence": int(form.get("formula_confidence", 1)),
        "institute_sheet": 1 if form.get("institute_sheet") else 0,
        "main_pyq": 1 if form.get("main_pyq") else 0,
        "adv_pyq": 1 if form.get("adv_pyq") else 0,
        "board_q": 1 if form.get("board_q") else 0,
        "practice_accuracy": int(form["practice_accuracy"]) if form.get("practice_accuracy") else None,
        "last_studied": form.get("last_studied") or None,
        "next_revision": form.get("next_revision") or None,
        "priority": form.get("priority", "Medium"),
        "notes": form.get("notes") or None,
    }
    db.update_topic(topic_id, fields)
    return redirect(url_for("topics_list"))


@app.route("/topics/reset", methods=["POST"])
def topics_reset():
    db.reset_topics()
    return redirect(url_for("topics_list"))


# ---------------------------------------------------------------------------
# Mock tests
# ---------------------------------------------------------------------------

@app.route("/mocks")
def mocks_list():
    mocks = db.get_all_mock_tests()
    return render_template("mocks.html", mocks=mocks)


@app.route("/mocks/<int:mock_id>/edit")
def mock_edit(mock_id):
    mock = db.get_mock_test(mock_id)
    if not mock:
        return redirect(url_for("mocks_list"))
    return render_template("mock_edit.html", mock=mock)


@app.route("/mocks/<int:mock_id>/update", methods=["POST"])
def mock_update(mock_id):
    form = request.form

    def to_int(name):
        v = form.get(name)
        return int(v) if v not in (None, "") else None

    attempted = to_int("attempted")
    correct = to_int("correct")
    accuracy = round((correct / attempted) * 100, 1) if attempted else None

    fields = {
        "test_date": form.get("test_date") or None,
        "test_type": form.get("test_type", "Full JEE Main"),
        "score": to_int("score"),
        "physics": to_int("physics"),
        "chemistry": to_int("chemistry"),
        "maths": to_int("maths"),
        "attempted": attempted,
        "correct": correct,
        "incorrect": to_int("incorrect"),
        "accuracy": accuracy,
        "error_pattern": form.get("error_pattern") or None,
        "next_actions": form.get("next_actions") or None,
    }
    db.update_mock_test(mock_id, fields)
    return redirect(url_for("mocks_list"))


@app.route("/mocks/reset", methods=["POST"])
def mocks_reset():
    db.reset_mock_tests()
    return redirect(url_for("mocks_list"))


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------

def phase_date_ranges(settings):
    """Best-effort start/end date for each of the 9 milestone phases, so the
    current one can be highlighted. Returns a list aligned with MILESTONES."""
    jan_exam = parse_date(settings.get("jan_exam_date")) or date(2027, 1, 24)
    april_exam = parse_date(settings.get("april_exam_date")) or date(2027, 4, 10)

    return [
        (date(2026, 10, 30), date(2026, 11, 1)),
        (date(2026, 11, 2), date(2026, 11, 22)),
        (date(2026, 11, 23), date(2026, 12, 13)),
        (date(2026, 12, 14), date(2026, 12, 31)),
        (date(2027, 1, 1), jan_exam),
        (jan_exam + timedelta(days=1), date(2027, 2, 15)),
        (date(2027, 2, 15), date(2027, 3, 31)),
        (april_exam - timedelta(days=21), april_exam),
        (april_exam + timedelta(days=1), None),
    ]


@app.route("/milestones")
def milestones_list():
    milestones = db.get_all_milestones()
    settings = db.get_settings()
    today = date.today()
    ranges = phase_date_ranges(settings)

    for m, (start, end) in zip(milestones, ranges):
        m["is_current"] = start <= today and (end is None or today <= end)

    return render_template("milestones.html", milestones=milestones)


@app.route("/milestones/reset", methods=["POST"])
def milestones_reset():
    db.reset_milestones()
    return redirect(url_for("milestones_list"))


# ---------------------------------------------------------------------------
# Full reset
# ---------------------------------------------------------------------------

@app.route("/reset-all", methods=["POST"])
def reset_all():
    db.reset_everything()
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
