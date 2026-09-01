# -*- coding: utf-8 -*-
"""
GymLog — แอปวางแผนและบันทึกการเวทเทรนนิ่ง / ออกกำลังกาย
Single-file Flask app + Tailwind CSS (CDN) + SQLite

รันด้วย:  python app.py   แล้วเปิด http://127.0.0.1:5000
"""

import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import (
    Flask, g, redirect, render_template, request, url_for, flash
)
from jinja2 import ChoiceLoader, DictLoader

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "gymlog.db")

app = Flask(__name__)
app.secret_key = "gymlog-dev-secret-key"

MUSCLE_GROUPS = ["อก", "หลัง", "ขา", "ไหล่", "แขน", "แกนกลาง", "คาร์ดิโอ"]


# ---------------------------------------------------------------- database --
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS exercises (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    muscle_group TEXT NOT NULL DEFAULT 'อื่น ๆ',
    equipment    TEXT DEFAULT '',
    note         TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS plans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    day_of_week TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id       INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    exercise_id   INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    target_sets   INTEGER NOT NULL DEFAULT 3,
    target_reps   INTEGER NOT NULL DEFAULT 10,
    target_weight REAL    NOT NULL DEFAULT 0,
    rest_sec      INTEGER NOT NULL DEFAULT 90,
    order_no      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS workouts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    name         TEXT NOT NULL DEFAULT 'เซสชันเทรน',
    plan_id      INTEGER REFERENCES plans(id) ON DELETE SET NULL,
    duration_min INTEGER NOT NULL DEFAULT 0,
    note         TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workout_sets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id  INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    set_no      INTEGER NOT NULL DEFAULT 1,
    weight      REAL    NOT NULL DEFAULT 0,
    reps        INTEGER NOT NULL DEFAULT 0,
    rpe         REAL    NOT NULL DEFAULT 0,
    done        INTEGER NOT NULL DEFAULT 1
);
"""

SEED_EXERCISES = [
    ("บาร์เบลสควอท", "ขา", "บาร์เบล", "ท่าหลักสำหรับขาและสะโพก"),
    ("เดดลิฟท์", "หลัง", "บาร์เบล", "ระวังหลังล่าง เก็บแกนกลางให้แน่น"),
    ("เบนช์เพรส", "อก", "บาร์เบล", "ท่าหลักสำหรับอก"),
    ("โอเวอร์เฮดเพรส", "ไหล่", "บาร์เบล", ""),
    ("บาร์เบลโรว์", "หลัง", "บาร์เบล", ""),
    ("พูลอัพ", "หลัง", "บอดี้เวท", "นับน้ำหนักตัวเป็น 0 หรือใส่น้ำหนักถ่วง"),
    ("ดิป", "อก", "บอดี้เวท", ""),
    ("อินไคลน์ ดัมเบลเพรส", "อก", "ดัมเบล", ""),
    ("แลตพูลดาวน์", "หลัง", "เคเบิล", ""),
    ("ดัมเบลไซด์แลทเทอรัลเรส", "ไหล่", "ดัมเบล", ""),
    ("ดัมเบลเคิร์ล", "แขน", "ดัมเบล", ""),
    ("ไทรเซปส์ พุชดาวน์", "แขน", "เคเบิล", ""),
    ("เลกเพรส", "ขา", "เครื่อง", ""),
    ("โรมาเนียน เดดลิฟท์", "ขา", "บาร์เบล", "เน้นแฮมสตริง"),
    ("ลันจ์", "ขา", "ดัมเบล", ""),
    ("แพลงก์", "แกนกลาง", "บอดี้เวท", "บันทึกวินาทีในช่องจำนวนครั้ง"),
    ("แฮงกิ้ง เลกเรส", "แกนกลาง", "บอดี้เวท", ""),
    ("วิ่งลู่", "คาร์ดิโอ", "เครื่อง", "บันทึกนาทีในช่องจำนวนครั้ง"),
]

SEED_PLANS = [
    ("Push Day (อก / ไหล่ / ไทรเซปส์)", "ดันทั้งหมด เน้นอกกับไหล่", "จันทร์", [
        ("เบนช์เพรส", 4, 8, 40),
        ("อินไคลน์ ดัมเบลเพรส", 3, 10, 16),
        ("โอเวอร์เฮดเพรส", 3, 10, 25),
        ("ดัมเบลไซด์แลทเทอรัลเรส", 3, 15, 8),
        ("ไทรเซปส์ พุชดาวน์", 3, 12, 20),
    ]),
    ("Pull Day (หลัง / ไบเซปส์)", "ดึงทั้งหมด เน้นความหนาและกว้างของหลัง", "พุธ", [
        ("เดดลิฟท์", 3, 5, 80),
        ("พูลอัพ", 4, 8, 0),
        ("บาร์เบลโรว์", 3, 10, 40),
        ("แลตพูลดาวน์", 3, 12, 40),
        ("ดัมเบลเคิร์ล", 3, 12, 10),
    ]),
    ("Leg Day (ขา / แกนกลาง)", "ขาและแกนกลางลำตัว", "ศุกร์", [
        ("บาร์เบลสควอท", 4, 8, 60),
        ("โรมาเนียน เดดลิฟท์", 3, 10, 50),
        ("เลกเพรส", 3, 12, 100),
        ("ลันจ์", 3, 12, 12),
        ("แพลงก์", 3, 60, 0),
    ]),
]


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)

    if db.execute("SELECT COUNT(*) c FROM exercises").fetchone()["c"] == 0:
        db.executemany(
            "INSERT INTO exercises (name, muscle_group, equipment, note) VALUES (?,?,?,?)",
            SEED_EXERCISES,
        )

    if db.execute("SELECT COUNT(*) c FROM plans").fetchone()["c"] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        for name, desc, dow, items in SEED_PLANS:
            cur = db.execute(
                "INSERT INTO plans (name, description, day_of_week, created_at) VALUES (?,?,?,?)",
                (name, desc, dow, now),
            )
            plan_id = cur.lastrowid
            for i, (ex_name, s, r, w) in enumerate(items):
                row = db.execute(
                    "SELECT id FROM exercises WHERE name = ?", (ex_name,)
                ).fetchone()
                if row:
                    db.execute(
                        "INSERT INTO plan_items (plan_id, exercise_id, target_sets,"
                        " target_reps, target_weight, rest_sec, order_no)"
                        " VALUES (?,?,?,?,?,?,?)",
                        (plan_id, row["id"], s, r, w, 90, i),
                    )
    db.commit()
    db.close()


# ----------------------------------------------------------------- helpers --
def to_float(value, default=0.0):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def to_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def today_str():
    return date.today().isoformat()


def thai_date(value):
    """2026-09-01 -> 1 ก.ย. 2569"""
    months = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
              "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return value or "-"
    return "%d %s %d" % (d.day, months[d.month - 1], d.year + 543)


app.jinja_env.filters["thaidate"] = thai_date


def workout_volume(workout_id):
    row = get_db().execute(
        "SELECT COALESCE(SUM(weight * reps), 0) v, COUNT(*) n"
        " FROM workout_sets WHERE workout_id = ? AND done = 1",
        (workout_id,),
    ).fetchone()
    return row["v"], row["n"]


def current_streak():
    db = get_db()
    days = {r["date"] for r in db.execute("SELECT DISTINCT date FROM workouts")}
    streak, cursor = 0, date.today()
    if cursor.isoformat() not in days:            # ยังไม่เทรนวันนี้ก็ยังไม่ตัดสตรีค
        cursor -= timedelta(days=1)
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


# ------------------------------------------------------------------ routes --
@app.route("/")
def dashboard():
    db = get_db()

    total_workouts = db.execute("SELECT COUNT(*) c FROM workouts").fetchone()["c"]
    total_volume = db.execute(
        "SELECT COALESCE(SUM(weight * reps), 0) v FROM workout_sets WHERE done = 1"
    ).fetchone()["v"]

    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    week = db.execute(
        "SELECT COUNT(DISTINCT w.id) c, COALESCE(SUM(s.weight * s.reps), 0) v"
        " FROM workouts w LEFT JOIN workout_sets s"
        "   ON s.workout_id = w.id AND s.done = 1"
        " WHERE w.date >= ?",
        (week_start,),
    ).fetchone()

    # กราฟปริมาณการเทรน 14 วันล่าสุด
    start = (date.today() - timedelta(days=13)).isoformat()
    rows = db.execute(
        "SELECT w.date d, COALESCE(SUM(s.weight * s.reps), 0) v"
        " FROM workouts w LEFT JOIN workout_sets s"
        "   ON s.workout_id = w.id AND s.done = 1"
        " WHERE w.date >= ? GROUP BY w.date",
        (start,),
    ).fetchall()
    by_date = {r["d"]: r["v"] for r in rows}
    chart = []
    for i in range(13, -1, -1):
        d = date.today() - timedelta(days=i)
        chart.append({"date": d.isoformat(), "label": "%d/%d" % (d.day, d.month),
                      "value": by_date.get(d.isoformat(), 0)})
    chart_max = max([c["value"] for c in chart] + [1])

    top_muscles = db.execute(
        "SELECT e.muscle_group g, COALESCE(SUM(s.weight * s.reps), 0) v, COUNT(*) n"
        " FROM workout_sets s JOIN exercises e ON e.id = s.exercise_id"
        " JOIN workouts w ON w.id = s.workout_id"
        " WHERE s.done = 1 AND w.date >= ?"
        " GROUP BY e.muscle_group ORDER BY v DESC",
        ((date.today() - timedelta(days=30)).isoformat(),),
    ).fetchall()
    muscle_max = max([m["v"] for m in top_muscles] + [1])

    recent = db.execute(
        "SELECT w.*, COALESCE(SUM(s.weight * s.reps), 0) volume,"
        "       COUNT(CASE WHEN s.done = 1 THEN 1 END) set_count"
        " FROM workouts w LEFT JOIN workout_sets s"
        "   ON s.workout_id = w.id AND s.done = 1"
        " GROUP BY w.id ORDER BY w.date DESC, w.id DESC LIMIT 6"
    ).fetchall()

    plans = db.execute(
        "SELECT p.*, COUNT(i.id) item_count FROM plans p"
        " LEFT JOIN plan_items i ON i.plan_id = p.id"
        " GROUP BY p.id ORDER BY p.id"
    ).fetchall()

    return render_template(
        "dashboard.html",
        total_workouts=total_workouts, total_volume=total_volume,
        week_count=week["c"], week_volume=week["v"], streak=current_streak(),
        chart=chart, chart_max=chart_max,
        top_muscles=top_muscles, muscle_max=muscle_max,
        recent=recent, plans=plans, today=today_str(),
    )


# --- คลังท่าออกกำลังกาย ---
@app.route("/exercises")
def exercises():
    db = get_db()
    mg = request.args.get("mg", "")
    q = request.args.get("q", "").strip()

    sql = ("SELECT e.*, COUNT(s.id) used FROM exercises e"
           " LEFT JOIN workout_sets s ON s.exercise_id = e.id WHERE 1=1")
    args = []
    if mg:
        sql += " AND e.muscle_group = ?"
        args.append(mg)
    if q:
        sql += " AND e.name LIKE ?"
        args.append("%" + q + "%")
    sql += " GROUP BY e.id ORDER BY e.muscle_group, e.name"

    return render_template("exercises.html", items=db.execute(sql, args).fetchall(),
                           groups=MUSCLE_GROUPS, mg=mg, q=q)


@app.post("/exercises/add")
def exercise_add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("กรุณากรอกชื่อท่า", "error")
        return redirect(url_for("exercises"))
    db = get_db()
    try:
        db.execute(
            "INSERT INTO exercises (name, muscle_group, equipment, note) VALUES (?,?,?,?)",
            (name, request.form.get("muscle_group") or "อื่น ๆ",
             request.form.get("equipment", "").strip(),
             request.form.get("note", "").strip()),
        )
        db.commit()
        flash("เพิ่มท่า \"%s\" เรียบร้อย" % name, "ok")
    except sqlite3.IntegrityError:
        flash("มีท่าชื่อนี้อยู่แล้ว", "error")
    return redirect(url_for("exercises"))


@app.post("/exercises/<int:ex_id>/delete")
def exercise_delete(ex_id):
    db = get_db()
    db.execute("DELETE FROM exercises WHERE id = ?", (ex_id,))
    db.commit()
    flash("ลบท่าออกกำลังกายแล้ว", "ok")
    return redirect(url_for("exercises"))


# --- แผนการเทรน ---
@app.route("/plans")
def plans():
    db = get_db()
    rows = db.execute(
        "SELECT p.*, COUNT(i.id) item_count,"
        "       COALESCE(SUM(i.target_sets), 0) total_sets"
        " FROM plans p LEFT JOIN plan_items i ON i.plan_id = p.id"
        " GROUP BY p.id ORDER BY p.id"
    ).fetchall()
    return render_template("plans.html", plans=rows)


@app.post("/plans/add")
def plan_add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("กรุณากรอกชื่อแผน", "error")
        return redirect(url_for("plans"))
    db = get_db()
    cur = db.execute(
        "INSERT INTO plans (name, description, day_of_week, created_at) VALUES (?,?,?,?)",
        (name, request.form.get("description", "").strip(),
         request.form.get("day_of_week", "").strip(),
         datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    return redirect(url_for("plan_detail", plan_id=cur.lastrowid))


@app.route("/plans/<int:plan_id>")
def plan_detail(plan_id):
    db = get_db()
    plan = db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    if plan is None:
        flash("ไม่พบแผนนี้", "error")
        return redirect(url_for("plans"))
    items = db.execute(
        "SELECT i.*, e.name, e.muscle_group, e.equipment FROM plan_items i"
        " JOIN exercises e ON e.id = i.exercise_id"
        " WHERE i.plan_id = ? ORDER BY i.order_no, i.id",
        (plan_id,),
    ).fetchall()
    all_ex = db.execute(
        "SELECT * FROM exercises ORDER BY muscle_group, name"
    ).fetchall()
    est_volume = sum(i["target_sets"] * i["target_reps"] * i["target_weight"] for i in items)
    return render_template("plan_detail.html", plan=plan, items=items,
                           all_ex=all_ex, est_volume=est_volume, today=today_str())


@app.post("/plans/<int:plan_id>/items/add")
def plan_item_add(plan_id):
    db = get_db()
    ex_id = to_int(request.form.get("exercise_id"))
    if not ex_id:
        flash("กรุณาเลือกท่าออกกำลังกาย", "error")
        return redirect(url_for("plan_detail", plan_id=plan_id))
    order_no = db.execute(
        "SELECT COALESCE(MAX(order_no), 0) + 1 n FROM plan_items WHERE plan_id = ?",
        (plan_id,),
    ).fetchone()["n"]
    db.execute(
        "INSERT INTO plan_items (plan_id, exercise_id, target_sets, target_reps,"
        " target_weight, rest_sec, order_no) VALUES (?,?,?,?,?,?,?)",
        (plan_id, ex_id, max(1, to_int(request.form.get("target_sets"), 3)),
         max(1, to_int(request.form.get("target_reps"), 10)),
         to_float(request.form.get("target_weight")),
         to_int(request.form.get("rest_sec"), 90), order_no),
    )
    db.commit()
    return redirect(url_for("plan_detail", plan_id=plan_id))


@app.post("/plan-items/<int:item_id>/delete")
def plan_item_delete(item_id):
    db = get_db()
    row = db.execute("SELECT plan_id FROM plan_items WHERE id = ?", (item_id,)).fetchone()
    db.execute("DELETE FROM plan_items WHERE id = ?", (item_id,))
    db.commit()
    return redirect(url_for("plan_detail", plan_id=row["plan_id"] if row else 0))


@app.post("/plans/<int:plan_id>/delete")
def plan_delete(plan_id):
    db = get_db()
    db.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
    db.commit()
    flash("ลบแผนการเทรนแล้ว", "ok")
    return redirect(url_for("plans"))


@app.post("/plans/<int:plan_id>/start")
def plan_start(plan_id):
    """สร้างเซสชันใหม่จากแผน พร้อมเซ็ตที่วางไว้ล่วงหน้า (ยังไม่ติ๊กว่าเสร็จ)"""
    db = get_db()
    plan = db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    if plan is None:
        flash("ไม่พบแผนนี้", "error")
        return redirect(url_for("plans"))

    d = request.form.get("date") or today_str()
    cur = db.execute(
        "INSERT INTO workouts (date, name, plan_id, duration_min, note, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (d, plan["name"], plan_id, 0, "",
         datetime.now().isoformat(timespec="seconds")),
    )
    w_id = cur.lastrowid
    items = db.execute(
        "SELECT * FROM plan_items WHERE plan_id = ? ORDER BY order_no, id", (plan_id,)
    ).fetchall()
    for it in items:
        for n in range(1, it["target_sets"] + 1):
            db.execute(
                "INSERT INTO workout_sets (workout_id, exercise_id, set_no, weight,"
                " reps, rpe, done) VALUES (?,?,?,?,?,?,0)",
                (w_id, it["exercise_id"], n, it["target_weight"], it["target_reps"], 0),
            )
    db.commit()
    flash("เริ่มเซสชันจากแผน \"%s\" แล้ว" % plan["name"], "ok")
    return redirect(url_for("workout_detail", workout_id=w_id))


# --- บันทึกการเทรน ---
@app.route("/workouts")
def workouts():
    db = get_db()
    rows = db.execute(
        "SELECT w.*, COALESCE(SUM(s.weight * s.reps), 0) volume,"
        "       COUNT(s.id) set_count,"
        "       COUNT(DISTINCT s.exercise_id) ex_count"
        " FROM workouts w LEFT JOIN workout_sets s"
        "   ON s.workout_id = w.id AND s.done = 1"
        " GROUP BY w.id ORDER BY w.date DESC, w.id DESC"
    ).fetchall()
    return render_template("workouts.html", workouts=rows, today=today_str())


@app.post("/workouts/add")
def workout_add():
    db = get_db()
    cur = db.execute(
        "INSERT INTO workouts (date, name, plan_id, duration_min, note, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (request.form.get("date") or today_str(),
         request.form.get("name", "").strip() or "เซสชันเทรน",
         None, to_int(request.form.get("duration_min")),
         request.form.get("note", "").strip(),
         datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    return redirect(url_for("workout_detail", workout_id=cur.lastrowid))


@app.route("/workouts/<int:workout_id>")
def workout_detail(workout_id):
    db = get_db()
    w = db.execute("SELECT * FROM workouts WHERE id = ?", (workout_id,)).fetchone()
    if w is None:
        flash("ไม่พบเซสชันนี้", "error")
        return redirect(url_for("workouts"))

    rows = db.execute(
        "SELECT s.*, e.name, e.muscle_group FROM workout_sets s"
        " JOIN exercises e ON e.id = s.exercise_id"
        " WHERE s.workout_id = ? ORDER BY s.id",
        (workout_id,),
    ).fetchall()

    groups, order = {}, []
    for r in rows:
        if r["exercise_id"] not in groups:
            groups[r["exercise_id"]] = {"name": r["name"], "muscle_group": r["muscle_group"],
                                        "sets": [], "volume": 0.0, "best": 0.0}
            order.append(r["exercise_id"])
        g_ = groups[r["exercise_id"]]
        g_["sets"].append(r)
        if r["done"]:
            g_["volume"] += r["weight"] * r["reps"]
            g_["best"] = max(g_["best"], r["weight"])
    blocks = [groups[i] for i in order]

    volume, done_sets = workout_volume(workout_id)
    all_ex = db.execute("SELECT * FROM exercises ORDER BY muscle_group, name").fetchall()
    return render_template("workout_detail.html", w=w, blocks=blocks, all_ex=all_ex,
                           volume=volume, done_sets=done_sets, total_sets=len(rows))


@app.post("/workouts/<int:workout_id>/update")
def workout_update(workout_id):
    db = get_db()
    db.execute(
        "UPDATE workouts SET date = ?, name = ?, duration_min = ?, note = ? WHERE id = ?",
        (request.form.get("date") or today_str(),
         request.form.get("name", "").strip() or "เซสชันเทรน",
         to_int(request.form.get("duration_min")),
         request.form.get("note", "").strip(), workout_id),
    )
    db.commit()
    flash("บันทึกข้อมูลเซสชันแล้ว", "ok")
    return redirect(url_for("workout_detail", workout_id=workout_id))


@app.post("/workouts/<int:workout_id>/delete")
def workout_delete(workout_id):
    db = get_db()
    db.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
    db.commit()
    flash("ลบเซสชันแล้ว", "ok")
    return redirect(url_for("workouts"))


@app.post("/workouts/<int:workout_id>/sets/add")
def set_add(workout_id):
    db = get_db()
    ex_id = to_int(request.form.get("exercise_id"))
    if not ex_id:
        flash("กรุณาเลือกท่าออกกำลังกาย", "error")
        return redirect(url_for("workout_detail", workout_id=workout_id))

    set_no = db.execute(
        "SELECT COALESCE(MAX(set_no), 0) + 1 n FROM workout_sets"
        " WHERE workout_id = ? AND exercise_id = ?",
        (workout_id, ex_id),
    ).fetchone()["n"]
    sets_to_add = max(1, to_int(request.form.get("count"), 1))
    for i in range(sets_to_add):
        db.execute(
            "INSERT INTO workout_sets (workout_id, exercise_id, set_no, weight, reps,"
            " rpe, done) VALUES (?,?,?,?,?,?,1)",
            (workout_id, ex_id, set_no + i, to_float(request.form.get("weight")),
             to_int(request.form.get("reps")), to_float(request.form.get("rpe"))),
        )
    db.commit()
    return redirect(url_for("workout_detail", workout_id=workout_id))


@app.post("/sets/<int:set_id>/save")
def set_save(set_id):
    db = get_db()
    row = db.execute("SELECT workout_id, done FROM workout_sets WHERE id = ?",
                     (set_id,)).fetchone()
    if row is None:
        return redirect(url_for("workouts"))

    action = request.form.get("action", "save")
    done = row["done"]
    if action == "toggle":
        done = 0 if row["done"] else 1
    elif action == "save":
        done = 1                                   # แก้ไขค่าแล้วถือว่าทำเซ็ตนี้แล้ว

    db.execute(
        "UPDATE workout_sets SET weight = ?, reps = ?, rpe = ?, done = ? WHERE id = ?",
        (to_float(request.form.get("weight")), to_int(request.form.get("reps")),
         to_float(request.form.get("rpe")), done, set_id),
    )
    db.commit()
    return redirect(url_for("workout_detail", workout_id=row["workout_id"]))


@app.post("/sets/<int:set_id>/delete")
def set_delete(set_id):
    db = get_db()
    row = db.execute("SELECT workout_id FROM workout_sets WHERE id = ?", (set_id,)).fetchone()
    db.execute("DELETE FROM workout_sets WHERE id = ?", (set_id,))
    db.commit()
    return redirect(url_for("workout_detail", workout_id=row["workout_id"] if row else 0))


# --- ความก้าวหน้า ---
@app.route("/progress")
def progress():
    db = get_db()
    all_ex = db.execute(
        "SELECT e.*, COUNT(s.id) used FROM exercises e"
        " LEFT JOIN workout_sets s ON s.exercise_id = e.id AND s.done = 1"
        " GROUP BY e.id HAVING used > 0 ORDER BY used DESC, e.name"
    ).fetchall()

    ex_id = to_int(request.args.get("ex_id"), all_ex[0]["id"] if all_ex else 0)
    ex = db.execute("SELECT * FROM exercises WHERE id = ?", (ex_id,)).fetchone()

    history, pr, chart_max = [], None, 1
    if ex is not None:
        history = db.execute(
            "SELECT w.date d, w.id wid, COUNT(s.id) sets,"
            "       COALESCE(SUM(s.weight * s.reps), 0) volume,"
            "       MAX(s.weight) best_weight, MAX(s.weight * s.reps) best_set"
            " FROM workout_sets s JOIN workouts w ON w.id = s.workout_id"
            " WHERE s.exercise_id = ? AND s.done = 1"
            " GROUP BY w.id ORDER BY w.date DESC, w.id DESC LIMIT 20",
            (ex_id,),
        ).fetchall()
        pr = db.execute(
            "SELECT MAX(s.weight) max_weight, MAX(s.reps) max_reps,"
            "       MAX(s.weight * s.reps) max_set_volume,"
            "       COALESCE(SUM(s.weight * s.reps), 0) total_volume, COUNT(*) total_sets"
            " FROM workout_sets s WHERE s.exercise_id = ? AND s.done = 1",
            (ex_id,),
        ).fetchone()
        chart_max = max([h["volume"] for h in history] + [1])

    return render_template("progress.html", all_ex=all_ex, ex=ex,
                           history=list(reversed(history)), pr=pr, chart_max=chart_max)


# --------------------------------------------------------------- templates --
LAYOUT = """
<!doctype html>
<html lang="th" class="h-full">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}GymLog{% endblock %} · GymLog</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;500;600;700&display=swap" rel="stylesheet">
<script>
tailwind.config = {
  theme: {
    extend: {
      fontFamily: { sans: ['IBM Plex Sans Thai', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
      colors: { brand: { 400: '#fbbf24', 500: '#f59e0b', 600: '#d97706' } }
    }
  }
}
</script>
<style>
  body { -webkit-font-smoothing: antialiased; }
  input[type=number]::-webkit-outer-spin-button,
  input[type=number]::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
  input[type=number] { -moz-appearance: textfield; }
</style>
</head>
<body class="h-full bg-slate-950 text-slate-100 font-sans">

<header class="sticky top-0 z-20 border-b border-slate-800 bg-slate-900/80 backdrop-blur">
  <div class="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
    <a href="{{ url_for('dashboard') }}" class="flex items-center gap-2 shrink-0">
      <span class="grid h-9 w-9 place-items-center rounded-xl bg-brand-500 text-lg">🏋️</span>
      <span class="text-lg font-bold tracking-tight">GymLog</span>
    </a>
    <nav class="ml-auto flex flex-wrap items-center gap-1 text-sm">
      {% set nav = [('dashboard','ภาพรวม'), ('plans','แผนเทรน'), ('workouts','บันทึก'),
                    ('exercises','คลังท่า'), ('progress','ความก้าวหน้า')] %}
      {% for endpoint, label in nav %}
        {% set active = request.endpoint == endpoint or request.path.startswith(url_for(endpoint)) and endpoint != 'dashboard' %}
        <a href="{{ url_for(endpoint) }}"
           class="rounded-lg px-3 py-2 font-medium transition
                  {{ 'bg-brand-500 text-slate-900' if active else 'text-slate-300 hover:bg-slate-800 hover:text-white' }}">
          {{ label }}
        </a>
      {% endfor %}
    </nav>
  </div>
</header>

<main class="mx-auto max-w-6xl px-4 py-6 pb-16">
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      <div class="mb-5 space-y-2">
        {% for cat, msg in messages %}
          <div class="rounded-xl border px-4 py-3 text-sm
                      {{ 'border-rose-500/40 bg-rose-500/10 text-rose-200' if cat == 'error'
                         else 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200' }}">
            {{ msg }}
          </div>
        {% endfor %}
      </div>
    {% endif %}
  {% endwith %}

  {% block content %}{% endblock %}
</main>

<footer class="border-t border-slate-800 py-6 text-center text-xs text-slate-500">
  GymLog · Flask + Tailwind CSS · ข้อมูลถูกเก็บในไฟล์ gymlog.db บนเครื่องคุณ
</footer>
</body>
</html>
"""

DASHBOARD = """
{% extends "layout.html" %}
{% block title %}ภาพรวม{% endblock %}
{% block content %}

<div class="mb-6 flex flex-wrap items-end justify-between gap-3">
  <div>
    <h1 class="text-2xl font-bold">ภาพรวมการเทรน</h1>
    <p class="mt-1 text-sm text-slate-400">สรุปผลและเริ่มเซสชันใหม่ได้จากที่นี่</p>
  </div>
  <form method="post" action="{{ url_for('workout_add') }}" class="flex gap-2">
    <input type="date" name="date" value="{{ today }}"
           class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm">
    <button class="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-brand-400">
      + บันทึกเซสชันเปล่า
    </button>
  </form>
</div>

<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
  {% set cards = [
    ('เซสชันทั้งหมด', total_workouts ~ ' ครั้ง', 'ตั้งแต่เริ่มใช้งาน', '📓'),
    ('ปริมาณรวม', '{:,.0f}'.format(total_volume) ~ ' กก.', 'น้ำหนัก × ครั้ง สะสม', '⚖️'),
    ('สัปดาห์นี้', week_count ~ ' ครั้ง', '{:,.0f}'.format(week_volume) ~ ' กก.', '📅'),
    ('สตรีคต่อเนื่อง', streak ~ ' วัน', 'เทรนติดต่อกัน', '🔥')
  ] %}
  {% for label, value, sub, icon in cards %}
    <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <div class="flex items-center justify-between">
        <span class="text-sm text-slate-400">{{ label }}</span><span>{{ icon }}</span>
      </div>
      <div class="mt-2 text-2xl font-bold text-brand-400">{{ value }}</div>
      <div class="mt-1 text-xs text-slate-500">{{ sub }}</div>
    </div>
  {% endfor %}
</div>

<div class="mt-6 grid gap-4 lg:grid-cols-3">
  <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5 lg:col-span-2">
    <h2 class="font-semibold">ปริมาณการเทรน 14 วันล่าสุด</h2>
    <div class="mt-5 flex h-44 items-end gap-1.5">
      {% for c in chart %}
        <div class="group flex flex-1 flex-col items-center justify-end gap-1">
          <span class="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100">
            {{ '{:,.0f}'.format(c.value) }}
          </span>
          <div class="w-full rounded-t {{ 'bg-brand-500' if c.value else 'bg-slate-800' }}"
               style="height: {{ (c.value / chart_max * 100) | round(1) if c.value else 3 }}%"></div>
          <span class="text-[10px] text-slate-500">{{ c.label }}</span>
        </div>
      {% endfor %}
    </div>
  </div>

  <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
    <h2 class="font-semibold">กลุ่มกล้ามเนื้อ 30 วัน</h2>
    {% if top_muscles %}
      <div class="mt-4 space-y-3">
        {% for m in top_muscles %}
          <div>
            <div class="flex justify-between text-xs">
              <span class="text-slate-300">{{ m.g }}</span>
              <span class="text-slate-500">{{ '{:,.0f}'.format(m.v) }} กก. · {{ m.n }} เซ็ต</span>
            </div>
            <div class="mt-1 h-2 rounded-full bg-slate-800">
              <div class="h-2 rounded-full bg-brand-500"
                   style="width: {{ (m.v / muscle_max * 100) | round(1) }}%"></div>
            </div>
          </div>
        {% endfor %}
      </div>
    {% else %}
      <p class="mt-4 text-sm text-slate-500">ยังไม่มีข้อมูลใน 30 วันล่าสุด</p>
    {% endif %}
  </div>
</div>

<div class="mt-6 grid gap-4 lg:grid-cols-2">
  <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
    <div class="flex items-center justify-between">
      <h2 class="font-semibold">เริ่มเทรนจากแผน</h2>
      <a href="{{ url_for('plans') }}" class="text-sm text-brand-400 hover:underline">จัดการแผน →</a>
    </div>
    <div class="mt-4 space-y-3">
      {% for p in plans %}
        <div class="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950 p-3">
          <div class="min-w-0 flex-1">
            <a href="{{ url_for('plan_detail', plan_id=p.id) }}"
               class="block truncate font-medium hover:text-brand-400">{{ p.name }}</a>
            <div class="text-xs text-slate-500">
              {{ p.item_count }} ท่า{% if p.day_of_week %} · {{ p.day_of_week }}{% endif %}
            </div>
          </div>
          <form method="post" action="{{ url_for('plan_start', plan_id=p.id) }}">
            <input type="hidden" name="date" value="{{ today }}">
            <button class="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-semibold text-slate-900 hover:bg-brand-400">
              เริ่มเลย
            </button>
          </form>
        </div>
      {% else %}
        <p class="text-sm text-slate-500">ยังไม่มีแผน — <a href="{{ url_for('plans') }}" class="text-brand-400">สร้างแผนแรก</a></p>
      {% endfor %}
    </div>
  </div>

  <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
    <div class="flex items-center justify-between">
      <h2 class="font-semibold">เซสชันล่าสุด</h2>
      <a href="{{ url_for('workouts') }}" class="text-sm text-brand-400 hover:underline">ดูทั้งหมด →</a>
    </div>
    <div class="mt-4 divide-y divide-slate-800">
      {% for w in recent %}
        <a href="{{ url_for('workout_detail', workout_id=w.id) }}"
           class="flex items-center gap-3 py-3 hover:opacity-80">
          <div class="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-slate-800 text-xs">
            {{ w.date[8:10] }}/{{ w.date[5:7] }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="truncate font-medium">{{ w.name }}</div>
            <div class="text-xs text-slate-500">{{ w.set_count }} เซ็ต · {{ w.date | thaidate }}</div>
          </div>
          <div class="text-right text-sm font-semibold text-brand-400">
            {{ '{:,.0f}'.format(w.volume) }}<span class="text-xs font-normal text-slate-500"> กก.</span>
          </div>
        </a>
      {% else %}
        <p class="py-3 text-sm text-slate-500">ยังไม่มีการบันทึก</p>
      {% endfor %}
    </div>
  </div>
</div>
{% endblock %}
"""

EXERCISES = """
{% extends "layout.html" %}
{% block title %}คลังท่า{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold">คลังท่าออกกำลังกาย</h1>
<p class="mt-1 text-sm text-slate-400">ท่าทั้งหมดที่ใช้ในแผนและบันทึกการเทรน</p>

<div class="mt-6 grid gap-4 lg:grid-cols-3">
  <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
    <h2 class="font-semibold">เพิ่มท่าใหม่</h2>
    <form method="post" action="{{ url_for('exercise_add') }}" class="mt-4 space-y-3">
      <div>
        <label class="text-xs text-slate-400">ชื่อท่า *</label>
        <input name="name" required placeholder="เช่น ฟรอนต์สควอท"
               class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none">
      </div>
      <div>
        <label class="text-xs text-slate-400">กลุ่มกล้ามเนื้อ</label>
        <select name="muscle_group"
                class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none">
          {% for g in groups %}<option value="{{ g }}">{{ g }}</option>{% endfor %}
          <option value="อื่น ๆ">อื่น ๆ</option>
        </select>
      </div>
      <div>
        <label class="text-xs text-slate-400">อุปกรณ์</label>
        <input name="equipment" placeholder="บาร์เบล / ดัมเบล / เครื่อง"
               class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none">
      </div>
      <div>
        <label class="text-xs text-slate-400">โน้ต</label>
        <textarea name="note" rows="2" placeholder="เทคนิค / ข้อควรระวัง"
                  class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"></textarea>
      </div>
      <button class="w-full rounded-lg bg-brand-500 py-2 text-sm font-semibold text-slate-900 hover:bg-brand-400">
        เพิ่มท่า
      </button>
    </form>
  </div>

  <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5 lg:col-span-2">
    <form method="get" class="flex flex-wrap gap-2">
      <input name="q" value="{{ q }}" placeholder="ค้นหาชื่อท่า…"
             class="min-w-40 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none">
      <select name="mg" class="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
        <option value="">ทุกกลุ่ม</option>
        {% for g in groups %}
          <option value="{{ g }}" {{ 'selected' if mg == g }}>{{ g }}</option>
        {% endfor %}
      </select>
      <button class="rounded-lg border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800">ค้นหา</button>
    </form>

    <div class="mt-4 overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="text-left text-xs uppercase text-slate-500">
          <tr class="border-b border-slate-800">
            <th class="py-2">ท่า</th><th>กลุ่ม</th><th>อุปกรณ์</th>
            <th class="text-right">ใช้แล้ว</th><th></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-800">
          {% for e in items %}
            <tr class="hover:bg-slate-950/60">
              <td class="py-2.5 pr-3">
                <div class="font-medium">{{ e.name }}</div>
                {% if e.note %}<div class="text-xs text-slate-500">{{ e.note }}</div>{% endif %}
              </td>
              <td class="pr-3">
                <span class="rounded-full bg-slate-800 px-2 py-0.5 text-xs">{{ e.muscle_group }}</span>
              </td>
              <td class="pr-3 text-slate-400">{{ e.equipment or '-' }}</td>
              <td class="pr-3 text-right text-slate-400">{{ e.used }} เซ็ต</td>
              <td class="text-right">
                <form method="post" action="{{ url_for('exercise_delete', ex_id=e.id) }}"
                      onsubmit="return confirm('ลบท่านี้? เซ็ตที่บันทึกไว้จะถูกลบด้วย')">
                  <button class="rounded-lg px-2 py-1 text-xs text-rose-400 hover:bg-rose-500/10">ลบ</button>
                </form>
              </td>
            </tr>
          {% else %}
            <tr><td colspan="5" class="py-6 text-center text-slate-500">ไม่พบท่าที่ค้นหา</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endblock %}
"""

PLANS = """
{% extends "layout.html" %}
{% block title %}แผนเทรน{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold">แผนการเทรน</h1>
<p class="mt-1 text-sm text-slate-400">วางโปรแกรมล่วงหน้า แล้วกด “เริ่มเทรน” เพื่อสร้างบันทึกอัตโนมัติ</p>

<div class="mt-6 grid gap-4 lg:grid-cols-3">
  <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
    <h2 class="font-semibold">สร้างแผนใหม่</h2>
    <form method="post" action="{{ url_for('plan_add') }}" class="mt-4 space-y-3">
      <div>
        <label class="text-xs text-slate-400">ชื่อแผน *</label>
        <input name="name" required placeholder="เช่น Upper Body A"
               class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none">
      </div>
      <div>
        <label class="text-xs text-slate-400">วันที่ตั้งใจเทรน</label>
        <select name="day_of_week"
                class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
          <option value="">ไม่ระบุ</option>
          {% for d in ['จันทร์','อังคาร','พุธ','พฤหัสบดี','ศุกร์','เสาร์','อาทิตย์'] %}
            <option>{{ d }}</option>
          {% endfor %}
        </select>
      </div>
      <div>
        <label class="text-xs text-slate-400">คำอธิบาย</label>
        <textarea name="description" rows="3" placeholder="เป้าหมายของแผนนี้"
                  class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"></textarea>
      </div>
      <button class="w-full rounded-lg bg-brand-500 py-2 text-sm font-semibold text-slate-900 hover:bg-brand-400">
        สร้างแผน
      </button>
    </form>
  </div>

  <div class="grid content-start gap-4 sm:grid-cols-2 lg:col-span-2">
    {% for p in plans %}
      <div class="flex flex-col rounded-2xl border border-slate-800 bg-slate-900 p-5">
        <div class="flex items-start justify-between gap-2">
          <a href="{{ url_for('plan_detail', plan_id=p.id) }}"
             class="font-semibold hover:text-brand-400">{{ p.name }}</a>
          {% if p.day_of_week %}
            <span class="shrink-0 rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-300">{{ p.day_of_week }}</span>
          {% endif %}
        </div>
        <p class="mt-1 line-clamp-2 text-sm text-slate-400">{{ p.description or 'ไม่มีคำอธิบาย' }}</p>
        <div class="mt-3 flex gap-4 text-xs text-slate-500">
          <span>🏋️ {{ p.item_count }} ท่า</span><span>🔢 {{ p.total_sets }} เซ็ต</span>
        </div>
        <div class="mt-4 flex gap-2">
          <form method="post" action="{{ url_for('plan_start', plan_id=p.id) }}" class="flex-1">
            <button class="w-full rounded-lg bg-brand-500 py-2 text-sm font-semibold text-slate-900 hover:bg-brand-400">
              เริ่มเทรน
            </button>
          </form>
          <a href="{{ url_for('plan_detail', plan_id=p.id) }}"
             class="rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800">แก้ไข</a>
          <form method="post" action="{{ url_for('plan_delete', plan_id=p.id) }}"
                onsubmit="return confirm('ลบแผนนี้?')">
            <button class="rounded-lg border border-slate-700 px-3 py-2 text-sm text-rose-400 hover:bg-rose-500/10">ลบ</button>
          </form>
        </div>
      </div>
    {% else %}
      <div class="rounded-2xl border border-dashed border-slate-800 p-10 text-center text-slate-500 sm:col-span-2">
        ยังไม่มีแผนการเทรน เริ่มสร้างจากฟอร์มด้านซ้าย
      </div>
    {% endfor %}
  </div>
</div>
{% endblock %}
"""

PLAN_DETAIL = """
{% extends "layout.html" %}
{% block title %}{{ plan.name }}{% endblock %}
{% block content %}
<a href="{{ url_for('plans') }}" class="text-sm text-slate-400 hover:text-brand-400">← กลับไปหน้าแผนทั้งหมด</a>

<div class="mt-3 flex flex-wrap items-end justify-between gap-3">
  <div>
    <h1 class="text-2xl font-bold">{{ plan.name }}</h1>
    <p class="mt-1 text-sm text-slate-400">
      {{ plan.description or 'ไม่มีคำอธิบาย' }}{% if plan.day_of_week %} · ทุกวัน{{ plan.day_of_week }}{% endif %}
    </p>
  </div>
  <form method="post" action="{{ url_for('plan_start', plan_id=plan.id) }}" class="flex gap-2">
    <input type="date" name="date" value="{{ today }}"
           class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm">
    <button class="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-brand-400">
      ▶ เริ่มเทรนตามแผนนี้
    </button>
  </form>
</div>

<div class="mt-4 grid gap-3 sm:grid-cols-3">
  {% set stats = [('จำนวนท่า', items|length ~ ' ท่า'),
                  ('เซ็ตรวม', items|sum(attribute='target_sets') ~ ' เซ็ต'),
                  ('ปริมาณเป้าหมาย', '{:,.0f}'.format(est_volume) ~ ' กก.')] %}
  {% for label, value in stats %}
    <div class="rounded-xl border border-slate-800 bg-slate-900 px-4 py-3">
      <div class="text-xs text-slate-400">{{ label }}</div>
      <div class="text-lg font-bold text-brand-400">{{ value }}</div>
    </div>
  {% endfor %}
</div>

<div class="mt-6 rounded-2xl border border-slate-800 bg-slate-900 p-5">
  <h2 class="font-semibold">ท่าในแผน</h2>
  <div class="mt-4 overflow-x-auto">
    <table class="w-full text-sm">
      <thead class="text-left text-xs uppercase text-slate-500">
        <tr class="border-b border-slate-800">
          <th class="py-2 w-10">#</th><th>ท่า</th><th class="text-center">เซ็ต</th>
          <th class="text-center">ครั้ง</th><th class="text-center">น้ำหนัก</th>
          <th class="text-center">พัก</th><th></th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-800">
        {% for i in items %}
          <tr>
            <td class="py-2.5 text-slate-500">{{ loop.index }}</td>
            <td class="pr-3">
              <div class="font-medium">{{ i.name }}</div>
              <div class="text-xs text-slate-500">{{ i.muscle_group }}{% if i.equipment %} · {{ i.equipment }}{% endif %}</div>
            </td>
            <td class="text-center">{{ i.target_sets }}</td>
            <td class="text-center">{{ i.target_reps }}</td>
            <td class="text-center">{{ '{:g}'.format(i.target_weight) }} กก.</td>
            <td class="text-center text-slate-400">{{ i.rest_sec }} วิ</td>
            <td class="text-right">
              <form method="post" action="{{ url_for('plan_item_delete', item_id=i.id) }}">
                <button class="rounded-lg px-2 py-1 text-xs text-rose-400 hover:bg-rose-500/10">ลบ</button>
              </form>
            </td>
          </tr>
        {% else %}
          <tr><td colspan="7" class="py-6 text-center text-slate-500">ยังไม่มีท่าในแผนนี้</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <form method="post" action="{{ url_for('plan_item_add', plan_id=plan.id) }}"
        class="mt-5 grid gap-3 rounded-xl border border-slate-800 bg-slate-950 p-4 sm:grid-cols-6">
    <div class="sm:col-span-2">
      <label class="text-xs text-slate-400">ท่าออกกำลังกาย</label>
      <select name="exercise_id" required
              class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm">
        {% for e in all_ex %}<option value="{{ e.id }}">{{ e.name }} ({{ e.muscle_group }})</option>{% endfor %}
      </select>
    </div>
    {% set fields = [('target_sets','เซ็ต','3'), ('target_reps','ครั้ง','10'),
                     ('target_weight','น้ำหนัก (กก.)','20'), ('rest_sec','พัก (วิ)','90')] %}
    {% for name, label, ph in fields %}
      <div>
        <label class="text-xs text-slate-400">{{ label }}</label>
        <input type="number" step="any" min="0" name="{{ name }}" value="{{ ph }}"
               class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm">
      </div>
    {% endfor %}
    <div class="sm:col-span-6">
      <button class="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-brand-400">
        + เพิ่มท่าเข้าแผน
      </button>
    </div>
  </form>
</div>
{% endblock %}
"""

WORKOUTS = """
{% extends "layout.html" %}
{% block title %}บันทึกการเทรน{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold">บันทึกการเทรน</h1>
<p class="mt-1 text-sm text-slate-400">ประวัติทุกเซสชันที่บันทึกไว้</p>

<form method="post" action="{{ url_for('workout_add') }}"
      class="mt-6 grid gap-3 rounded-2xl border border-slate-800 bg-slate-900 p-5 sm:grid-cols-5">
  <div class="sm:col-span-2">
    <label class="text-xs text-slate-400">ชื่อเซสชัน</label>
    <input name="name" placeholder="เช่น Upper Body"
           class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
  </div>
  <div>
    <label class="text-xs text-slate-400">วันที่</label>
    <input type="date" name="date" value="{{ today }}"
           class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
  </div>
  <div>
    <label class="text-xs text-slate-400">ระยะเวลา (นาที)</label>
    <input type="number" min="0" name="duration_min" value="60"
           class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
  </div>
  <div class="flex items-end">
    <button class="w-full rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-brand-400">
      + สร้างเซสชัน
    </button>
  </div>
</form>

<div class="mt-6 space-y-3">
  {% for w in workouts %}
    <div class="flex flex-wrap items-center gap-4 rounded-2xl border border-slate-800 bg-slate-900 p-4">
      <div class="grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-slate-800">
        <span class="text-lg font-bold leading-none">{{ w.date[8:10] }}</span>
        <span class="text-[10px] text-slate-400">{{ w.date[5:7] }}/{{ w.date[0:4] }}</span>
      </div>
      <div class="min-w-0 flex-1">
        <a href="{{ url_for('workout_detail', workout_id=w.id) }}"
           class="font-semibold hover:text-brand-400">{{ w.name }}</a>
        <div class="mt-0.5 text-xs text-slate-500">
          {{ w.date | thaidate }}
          {% if w.duration_min %} · {{ w.duration_min }} นาที{% endif %}
          {% if w.note %} · {{ w.note }}{% endif %}
        </div>
      </div>
      <div class="flex gap-5 text-center text-xs">
        <div><div class="text-base font-bold text-slate-100">{{ w.ex_count }}</div><div class="text-slate-500">ท่า</div></div>
        <div><div class="text-base font-bold text-slate-100">{{ w.set_count }}</div><div class="text-slate-500">เซ็ต</div></div>
        <div><div class="text-base font-bold text-brand-400">{{ '{:,.0f}'.format(w.volume) }}</div><div class="text-slate-500">กก.</div></div>
      </div>
      <div class="flex gap-2">
        <a href="{{ url_for('workout_detail', workout_id=w.id) }}"
           class="rounded-lg border border-slate-700 px-3 py-1.5 text-sm hover:bg-slate-800">เปิด</a>
        <form method="post" action="{{ url_for('workout_delete', workout_id=w.id) }}"
              onsubmit="return confirm('ลบเซสชันนี้?')">
          <button class="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-rose-400 hover:bg-rose-500/10">ลบ</button>
        </form>
      </div>
    </div>
  {% else %}
    <div class="rounded-2xl border border-dashed border-slate-800 p-12 text-center text-slate-500">
      ยังไม่มีบันทึก — สร้างเซสชันด้านบน หรือเริ่มจาก
      <a href="{{ url_for('plans') }}" class="text-brand-400">แผนการเทรน</a>
    </div>
  {% endfor %}
</div>
{% endblock %}
"""

WORKOUT_DETAIL = """
{% extends "layout.html" %}
{% block title %}{{ w.name }}{% endblock %}
{% block content %}
<a href="{{ url_for('workouts') }}" class="text-sm text-slate-400 hover:text-brand-400">← กลับไปหน้าบันทึกทั้งหมด</a>

<div class="mt-3 grid gap-4 lg:grid-cols-4">
  <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5 lg:col-span-3">
    <h1 class="text-2xl font-bold">{{ w.name }}</h1>
    <p class="mt-1 text-sm text-slate-400">{{ w.date | thaidate }}</p>

    <div class="mt-4 grid gap-3 sm:grid-cols-3">
      {% set stats = [('ปริมาณรวม', '{:,.0f}'.format(volume) ~ ' กก.'),
                      ('เซ็ตที่ทำแล้ว', done_sets ~ ' / ' ~ total_sets),
                      ('ระยะเวลา', w.duration_min ~ ' นาที')] %}
      {% for label, value in stats %}
        <div class="rounded-xl border border-slate-800 bg-slate-950 px-4 py-3">
          <div class="text-xs text-slate-400">{{ label }}</div>
          <div class="text-lg font-bold text-brand-400">{{ value }}</div>
        </div>
      {% endfor %}
    </div>
  </div>

  <form method="post" action="{{ url_for('workout_update', workout_id=w.id) }}"
        class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900 p-5">
    <h2 class="text-sm font-semibold">แก้ไขข้อมูลเซสชัน</h2>
    <input name="name" value="{{ w.name }}"
           class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
    <input type="date" name="date" value="{{ w.date }}"
           class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
    <input type="number" min="0" name="duration_min" value="{{ w.duration_min }}" placeholder="นาที"
           class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
    <textarea name="note" rows="2" placeholder="โน้ต / ความรู้สึกวันนี้"
              class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">{{ w.note }}</textarea>
    <button class="w-full rounded-lg border border-slate-700 py-2 text-sm hover:bg-slate-800">บันทึก</button>
  </form>
</div>

<div class="mt-6 space-y-4">
  {% for b in blocks %}
    <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 class="font-semibold">{{ b.name }}</h2>
          <span class="text-xs text-slate-500">{{ b.muscle_group }}</span>
        </div>
        <div class="text-right text-xs text-slate-500">
          ปริมาณ <span class="font-semibold text-brand-400">{{ '{:,.0f}'.format(b.volume) }}</span> กก.
          · หนักสุด {{ '{:g}'.format(b.best) }} กก.
        </div>
      </div>

      <div class="mt-3 space-y-2">
        {% for s in b.sets %}
          <form method="post" action="{{ url_for('set_save', set_id=s.id) }}"
                class="flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2
                       {{ 'border-emerald-500/30 bg-emerald-500/5' if s.done else 'border-slate-800 bg-slate-950' }}">
            <span class="w-14 shrink-0 text-xs text-slate-400">เซ็ต {{ s.set_no }}</span>
            <label class="flex items-center gap-1 text-xs text-slate-400">
              <input type="number" step="0.5" min="0" name="weight" value="{{ '{:g}'.format(s.weight) }}"
                     class="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100">กก.
            </label>
            <span class="text-slate-600">×</span>
            <label class="flex items-center gap-1 text-xs text-slate-400">
              <input type="number" min="0" name="reps" value="{{ s.reps }}"
                     class="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100">ครั้ง
            </label>
            <label class="flex items-center gap-1 text-xs text-slate-400">
              RPE <input type="number" step="0.5" min="0" max="10" name="rpe" value="{{ '{:g}'.format(s.rpe) }}"
                     class="w-16 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100">
            </label>
            <span class="ml-auto text-xs text-slate-500">
              {{ '{:,.0f}'.format(s.weight * s.reps) }} กก.
            </span>
            <button name="action" value="save"
                    class="rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-semibold text-slate-900 hover:bg-brand-400">
              บันทึก
            </button>
            <button name="action" value="toggle" formnovalidate
                    class="rounded-lg border px-3 py-1.5 text-xs
                           {{ 'border-emerald-500/40 text-emerald-300' if s.done else 'border-slate-700 text-slate-400' }}">
              {{ '✓ ทำแล้ว' if s.done else 'ยังไม่ทำ' }}
            </button>
            <button formaction="{{ url_for('set_delete', set_id=s.id) }}" formnovalidate
                    class="rounded-lg px-2 py-1.5 text-xs text-rose-400 hover:bg-rose-500/10">✕</button>
          </form>
        {% endfor %}
      </div>
    </div>
  {% else %}
    <div class="rounded-2xl border border-dashed border-slate-800 p-10 text-center text-slate-500">
      ยังไม่มีเซ็ตในเซสชันนี้ — เพิ่มด้านล่างได้เลย
    </div>
  {% endfor %}
</div>

<form method="post" action="{{ url_for('set_add', workout_id=w.id) }}"
      class="mt-6 grid gap-3 rounded-2xl border border-slate-800 bg-slate-900 p-5 sm:grid-cols-6">
  <h2 class="font-semibold sm:col-span-6">เพิ่มเซ็ต</h2>
  <div class="sm:col-span-2">
    <label class="text-xs text-slate-400">ท่า</label>
    <select name="exercise_id" required
            class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
      {% for e in all_ex %}<option value="{{ e.id }}">{{ e.name }} ({{ e.muscle_group }})</option>{% endfor %}
    </select>
  </div>
  {% set fields = [('weight','น้ำหนัก (กก.)','20','0.5'), ('reps','จำนวนครั้ง','10','1'),
                   ('rpe','RPE (0-10)','8','0.5'), ('count','จำนวนเซ็ต','1','1')] %}
  {% for name, label, val, step in fields %}
    <div>
      <label class="text-xs text-slate-400">{{ label }}</label>
      <input type="number" step="{{ step }}" min="0" name="{{ name }}" value="{{ val }}"
             class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
    </div>
  {% endfor %}
  <div class="sm:col-span-6">
    <button class="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-brand-400">
      + บันทึกเซ็ต
    </button>
  </div>
</form>
{% endblock %}
"""

PROGRESS = """
{% extends "layout.html" %}
{% block title %}ความก้าวหน้า{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold">ความก้าวหน้ารายท่า</h1>
<p class="mt-1 text-sm text-slate-400">ดูสถิติส่วนตัว (PR) และแนวโน้มปริมาณการเทรนของแต่ละท่า</p>

{% if all_ex %}
  <form method="get" class="mt-6 flex flex-wrap gap-2">
    <select name="ex_id" onchange="this.form.submit()"
            class="min-w-56 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm">
      {% for e in all_ex %}
        <option value="{{ e.id }}" {{ 'selected' if ex and ex.id == e.id }}>
          {{ e.name }} — {{ e.used }} เซ็ต
        </option>
      {% endfor %}
    </select>
    <button class="rounded-lg border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800">ดู</button>
  </form>

  <div class="mt-4 grid gap-3 sm:grid-cols-4">
    {% set cards = [('น้ำหนักสูงสุด', '{:g}'.format(pr.max_weight or 0) ~ ' กก.'),
                    ('เซ็ตหนักสุด', '{:,.0f}'.format(pr.max_set_volume or 0) ~ ' กก.'),
                    ('ปริมาณสะสม', '{:,.0f}'.format(pr.total_volume or 0) ~ ' กก.'),
                    ('เซ็ตทั้งหมด', (pr.total_sets or 0) ~ ' เซ็ต')] %}
    {% for label, value in cards %}
      <div class="rounded-2xl border border-slate-800 bg-slate-900 p-4">
        <div class="text-xs text-slate-400">{{ label }}</div>
        <div class="mt-1 text-xl font-bold text-brand-400">{{ value }}</div>
      </div>
    {% endfor %}
  </div>

  <div class="mt-6 rounded-2xl border border-slate-800 bg-slate-900 p-5">
    <h2 class="font-semibold">ปริมาณต่อเซสชัน — {{ ex.name }}</h2>
    <div class="mt-5 flex h-44 items-end gap-2">
      {% for h in history %}
        <div class="group flex flex-1 flex-col items-center justify-end gap-1">
          <span class="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100">
            {{ '{:,.0f}'.format(h.volume) }}
          </span>
          <div class="w-full rounded-t bg-brand-500"
               style="height: {{ (h.volume / chart_max * 100) | round(1) }}%"></div>
          <span class="text-[10px] text-slate-500">{{ h.d[8:10] }}/{{ h.d[5:7] }}</span>
        </div>
      {% else %}
        <p class="text-sm text-slate-500">ยังไม่มีข้อมูล</p>
      {% endfor %}
    </div>
  </div>

  <div class="mt-6 overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900 p-5">
    <h2 class="font-semibold">ประวัติล่าสุด</h2>
    <table class="mt-4 w-full text-sm">
      <thead class="text-left text-xs uppercase text-slate-500">
        <tr class="border-b border-slate-800">
          <th class="py-2">วันที่</th><th class="text-center">เซ็ต</th>
          <th class="text-center">น้ำหนักสูงสุด</th><th class="text-center">เซ็ตที่ดีที่สุด</th>
          <th class="text-right">ปริมาณ</th><th></th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-800">
        {% for h in history | reverse %}
          <tr>
            <td class="py-2.5">{{ h.d | thaidate }}</td>
            <td class="text-center">{{ h.sets }}</td>
            <td class="text-center">{{ '{:g}'.format(h.best_weight) }} กก.</td>
            <td class="text-center">{{ '{:,.0f}'.format(h.best_set) }} กก.</td>
            <td class="text-right font-semibold text-brand-400">{{ '{:,.0f}'.format(h.volume) }} กก.</td>
            <td class="text-right">
              <a href="{{ url_for('workout_detail', workout_id=h.wid) }}"
                 class="text-xs text-slate-400 hover:text-brand-400">เปิด →</a>
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% else %}
  <div class="mt-6 rounded-2xl border border-dashed border-slate-800 p-12 text-center text-slate-500">
    ยังไม่มีข้อมูลการเทรน — เริ่ม<a href="{{ url_for('plans') }}" class="text-brand-400">เทรนตามแผน</a>ก่อน
  </div>
{% endif %}
{% endblock %}
"""

app.jinja_loader = ChoiceLoader([
    DictLoader({
        "layout.html": LAYOUT,
        "dashboard.html": DASHBOARD,
        "exercises.html": EXERCISES,
        "plans.html": PLANS,
        "plan_detail.html": PLAN_DETAIL,
        "workouts.html": WORKOUTS,
        "workout_detail.html": WORKOUT_DETAIL,
        "progress.html": PROGRESS,
    }),
    app.jinja_loader,
])


if __name__ == "__main__":
    init_db()
    # พอร์ต 5000 บน macOS มักถูก AirPlay ใช้อยู่ จึงใช้ 5001 เป็นค่าเริ่มต้น
    port = int(os.environ.get("PORT", 5001))
    print("GymLog พร้อมใช้งานที่ http://127.0.0.1:%d  (ฐานข้อมูล: %s)" % (port, DB_PATH))
    app.run(debug=True, host="127.0.0.1", port=port)
