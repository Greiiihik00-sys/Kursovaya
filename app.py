from __future__ import annotations

import datetime as dt
import random
import time
from pathlib import Path

import pyodbc
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "autoflow.accdb"

CONN_STR = (
    r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
    rf"DBQ={DB_PATH};"
)

app = Flask(__name__)


def get_conn() -> pyodbc.Connection:
    last_error = None
    for _ in range(2):
        try:
            return pyodbc.connect(CONN_STR, autocommit=False, timeout=2)
        except pyodbc.Error as e:
            last_error = e
            time.sleep(0.1)
    raise last_error


def table_exists(cur: pyodbc.Cursor, table_name: str) -> bool:
    return len(cur.tables(table=table_name, tableType="TABLE").fetchall()) > 0


def ensure_indexes(cur: pyodbc.Cursor) -> None:
    try:
        cur.execute("CREATE UNIQUE INDEX ux_vehicles_id ON vehicles ([id])")
    except pyodbc.Error:
        pass
    try:
        cur.execute("CREATE INDEX ix_deals_vehicle_id ON deals ([vehicle_id])")
    except pyodbc.Error:
        pass


def is_vehicles_empty(cur: pyodbc.Cursor) -> bool:
    return int(cur.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]) == 0


def seed_vehicles(cur: pyodbc.Cursor) -> None:
    rows = [
        (1, "LADA", "Priora", 2011, "XTA217230800555777", 350000, "В наличии", "Козлов Е.Д.", 350000, "1.6 л / 98 л.с."),
        (2, "LADA", "Vesta", 2020, "XTA218010800789012", 890000, "Резерв", "Петрова И.С.", 28000, "1.8 л / 122 л.с."),
        (3, "Toyota", "Camry", 2018, "JT2BF22K610012345", 1850000, "В наличии", "Петров С.М.", 75000, "2.5 л / 181 л.с."),
        (4, "KIA", "Rio", 2019, "Z94C251BBKR123456", 1090000, "Продано", "Соловьев Н.А.", 89000, "1.6 л / 123 л.с."),
        (5, "Renault", "Logan", 2017, "X7L4SRAV457654321", 780000, "В наличии", "Михайлов И.И.", 119000, "1.6 л / 102 л.с."),
    ]
    cur.executemany(
        """
        INSERT INTO vehicles ([id], [brand], [model], [year], [vin], [price], [status], [owner_name], [mileage], [engine])
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def ensure_tables() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"База не найдена: {DB_PATH}. Запусти create_access_db.py")

    with get_conn() as conn:
        cur = conn.cursor()

        if not table_exists(cur, "vehicles"):
            cur.execute(
                """
                CREATE TABLE vehicles (
                    [id] LONG,
                    [brand] TEXT(50),
                    [model] TEXT(80),
                    [year] LONG,
                    [vin] TEXT(40),
                    [price] DOUBLE,
                    [status] TEXT(20),
                    [owner_name] TEXT(100),
                    [mileage] LONG,
                    [engine] TEXT(80)
                )
                """
            )

        if not table_exists(cur, "deals"):
            cur.execute(
                """
                CREATE TABLE deals (
                    [id] COUNTER PRIMARY KEY,
                    [vehicle_id] LONG,
                    [brand] TEXT(50),
                    [model] TEXT(80),
                    [price] DOUBLE,
                    [deal_date] DATETIME,
                    [note] TEXT(255)
                )
                """
            )

        ensure_indexes(cur)
        if is_vehicles_empty(cur):
            seed_vehicles(cur)
        conn.commit()


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/cars/<path:filename>")
def cars_static(filename: str):
    return send_from_directory(BASE_DIR / "cars", filename)


@app.route("/api/vehicles", methods=["GET"])
def get_vehicles():
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            rows = cur.execute(
                """
                SELECT [id], [brand], [model], [year], [vin], [price], [status], [owner_name], [mileage], [engine]
                FROM vehicles
                ORDER BY [id]
                """
            ).fetchall()
    except pyodbc.Error:
        return jsonify({"ok": False, "message": "БД Access занята или недоступна. Закрой Access и повтори."}), 503

    return jsonify(
        [
            {
                "id": int(r[0]),
                "brand": r[1],
                "model": r[2],
                "year": int(r[3]),
                "vin": r[4],
                "price": int(r[5]),
                "status": r[6],
                "owner": r[7],
                "mileage": int(r[8]),
                "engine": r[9],
                "history": ["История: ведется менеджером"],
            }
            for r in rows
        ]
    )


@app.route("/api/vehicles/random", methods=["POST"])
def add_random_vehicle():
    templates = [
        {"brand": "LADA", "model": "Granta", "engine": "1.6 л / 90 л.с.", "base": 940000},
        {"brand": "LADA", "model": "Vesta", "engine": "1.6 л / 106 л.с.", "base": 1320000},
        {"brand": "KIA", "model": "Rio", "engine": "1.6 л / 123 л.с.", "base": 1290000},
        {"brand": "Renault", "model": "Logan", "engine": "1.6 л / 102 л.с.", "base": 890000},
        {"brand": "Volkswagen", "model": "Polo", "engine": "1.6 л / 110 л.с.", "base": 1280000},
        {"brand": "Toyota", "model": "Corolla", "engine": "1.6 л / 122 л.с.", "base": 1780000},
        {"brand": "Toyota", "model": "Camry", "engine": "2.5 л / 181 л.с.", "base": 2850000},
    ]
    t = random.choice(templates)
    year = random.randint(2016, 2025)
    price = max(500000, t["base"] - (2026 - year) * 55000 + random.randint(-50000, 110000))
    vin = f"XTA{str(int(dt.datetime.now().timestamp() * 1000))[-13:]}"

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            new_id = int(cur.execute("SELECT IIF(MAX([id]) IS NULL, 1, MAX([id]) + 1) FROM vehicles").fetchone()[0])
            cur.execute(
                """
                INSERT INTO vehicles ([id], [brand], [model], [year], [vin], [price], [status], [owner_name], [mileage], [engine])
                VALUES (?, ?, ?, ?, ?, ?, 'В наличии', 'Новый клиент', ?, ?)
                """,
                (new_id, t["brand"], t["model"], year, vin, float(price), random.randint(12000, 180000), t["engine"]),
            )
            conn.commit()
    except pyodbc.Error:
        return jsonify({"ok": False, "message": "Не удалось записать в Access. Закрой Access и повтори."}), 503
    return jsonify({"ok": True, "vehicle_id": new_id})


@app.route("/api/vehicles/<int:vehicle_id>/status", methods=["PATCH"])
def set_status(vehicle_id: int):
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status not in {"В наличии", "Резерв", "Продано"}:
        return jsonify({"ok": False, "message": "Некорректный статус"}), 400

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            changed = cur.execute("UPDATE vehicles SET [status] = ? WHERE [id] = ?", (status, vehicle_id)).rowcount
            if changed == 0:
                return jsonify({"ok": False, "message": "Авто не найдено"}), 404
            conn.commit()
    except pyodbc.Error:
        return jsonify({"ok": False, "message": "Access временно недоступен. Закрой Access и повтори."}), 503
    return jsonify({"ok": True})


@app.route("/api/deals/random", methods=["POST"])
def random_deal():
    payload = request.get_json(silent=True) or {}
    note = payload.get("note", "Случайная сделка из CRM")

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            pool = cur.execute(
                "SELECT [id], [brand], [model], [price] FROM vehicles WHERE [status]='В наличии'"
            ).fetchall()
            if not pool:
                return jsonify({"ok": False, "message": "Нет автомобилей в наличии"}), 400

            chosen = random.choice(pool)
            vehicle_id, brand, model, price = int(chosen[0]), chosen[1], chosen[2], int(chosen[3])
            cur.execute("UPDATE vehicles SET [status]='Продано' WHERE [id]=?", (vehicle_id,))
            cur.execute(
                """
                INSERT INTO deals ([vehicle_id], [brand], [model], [price], [deal_date], [note])
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (vehicle_id, brand, model, float(price), dt.datetime.now(), note),
            )
            conn.commit()
    except pyodbc.Error:
        return jsonify({"ok": False, "message": "Сделка не записана: Access занят или недоступен."}), 503

    return jsonify({"ok": True, "message": f"Продан {brand} {model}", "deal": {"vehicle_id": vehicle_id}})


if __name__ == "__main__":
    DB_DIR.mkdir(exist_ok=True)
    ensure_tables()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=False)
