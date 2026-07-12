# -*- coding: utf-8 -*-
"""
update_egg_price.py

Alur:
1. Ambil data harga telur dari sumber web
2. Simpan/update ke MongoDB Atlas
3. Ambil data dari MongoDB
4. Buat file JSON report_harga_telur.json
5. GitHub Actions commit file JSON tersebut
"""

import os
import re
import json
import math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient, DESCENDING


# =========================
# KONFIGURASI
# =========================

SUNEGG_URL = "https://sunegg.id/indeks-harga-telur"

DB_NAME = os.environ.get("MONGO_DB_NAME", "harga_telur_db")
COLLECTION_NAME = os.environ.get("MONGO_COLLECTION", "harga_harian")
MONGODB_URI = os.environ.get("MONGODB_URI", "")

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "report_harga_telur.json"

WILAYAH_DEFAULT = [
    "Jabar-DKI",
    "Jawa Tengah",
    "Jawa Timur",
    "Luar Jawa",
]

TZ_JAKARTA = ZoneInfo("Asia/Jakarta")


# =========================
# HELPER DASAR
# =========================

def log(message):
    now = datetime.now(TZ_JAKARTA).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}")


def today_jakarta():
    return datetime.now(TZ_JAKARTA).strftime("%Y-%m-%d")


def now_iso():
    return datetime.now(TZ_JAKARTA).isoformat()


def to_int(value, default=0):
    try:
        if value is None:
            return default

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return int(round(value))

        text = str(value)
        text = text.replace("Rp", "")
        text = text.replace("rp", "")
        text = text.replace(".", "")
        text = text.replace(",", "")
        text = text.strip()

        return int(text)
    except Exception:
        return default


def safe_round(value, digit=2):
    try:
        if value is None:
            return 0
        if math.isnan(value):
            return 0
        return round(value, digit)
    except Exception:
        return 0


def format_label_tanggal(tanggal):
    try:
        date_obj = datetime.strptime(str(tanggal), "%Y-%m-%d")
    except Exception:
        return str(tanggal)

    bulan = {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "Mei",
        6: "Jun",
        7: "Jul",
        8: "Agu",
        9: "Sep",
        10: "Okt",
        11: "Nov",
        12: "Des",
    }

    return f"{date_obj.day:02d} {bulan[date_obj.month]}"


def normalize_chart_value(harga, min_harga, max_harga):
    if max_harga == min_harga:
        return 0.5

    value = (harga - min_harga) / (max_harga - min_harga)

    # Supaya grafik tidak terlalu nempel bawah/atas
    return safe_round(0.15 + (value * 0.75), 2)

# =========================
# AMBIL DATA DARI WEB
# =========================

def fetch_halaman(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        raise Exception(f"Gagal mengambil halaman SunEgg: {response.status_code}")

    return response.text


def ambil_angka_harga(text):
    if not text:
        return []

    pola = r"(?:Rp\s*)?(\d{1,3}(?:[.,]\d{3})+|\d{5,6})"
    matches = re.findall(pola, text)

    hasil = []

    for item in matches:
        angka = to_int(item)

        if 10000 <= angka <= 100000:
            hasil.append(angka)

    return hasil


def cari_harga_dekat_wilayah(text, wilayah):
    if not text or not wilayah:
        return None

    index = text.lower().find(wilayah.lower())

    if index == -1:
        return None

    potongan = text[index:index + 300]
    angka = ambil_angka_harga(potongan)

    if not angka:
        return None

    return angka[0]


def scrape_indeks_harga():
    """
    Mengambil data dari SunEgg.

    Catatan:
    Jika GitHub Actions kena 403, fungsi ini akan gagal.
    Script tetap lanjut membuat report dari data MongoDB terakhir.
    """

    log("Mulai mengambil data dari SunEgg")

    html = fetch_halaman(SUNEGG_URL)

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    semua_harga = ambil_angka_harga(text)

    if not semua_harga:
        raise Exception("Tidak menemukan angka harga pada halaman SunEgg")

    tanggal = today_jakarta()
    created_at = now_iso()

    data = []

    harga_nasional = semua_harga[0]

    data.append({
        "tanggal": tanggal,
        "wilayah": "Nasional",
        "harga": harga_nasional,
        "sumber": SUNEGG_URL,
        "created_at": created_at,
        "updated_at": created_at,
    })

    for wilayah in WILAYAH_DEFAULT:
        harga_wilayah = cari_harga_dekat_wilayah(text, wilayah)

        if harga_wilayah is not None:
            data.append({
                "tanggal": tanggal,
                "wilayah": wilayah,
                "harga": harga_wilayah,
                "sumber": SUNEGG_URL,
                "created_at": created_at,
                "updated_at": created_at,
            })

    log(f"Data hasil scraping: {len(data)} record")

    return data


# =========================
# MONGODB
# =========================

def koneksi_mongodb():
    if not MONGODB_URI:
        raise Exception("MONGODB_URI belum diatur di environment variable")

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=20000)

    # Test koneksi
    client.admin.command("ping")

    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    log("Koneksi MongoDB Atlas berhasil")

    return client, collection


def simpan_ke_mongodb(collection, data):
    if not data:
        log("Tidak ada data baru untuk disimpan ke MongoDB")
        return

    total_upsert = 0

    for item in data:
        collection.update_one(
            {
                "tanggal": item["tanggal"],
                "wilayah": item["wilayah"],
            },
            {
                "$set": {
                    "harga": item["harga"],
                    "sumber": item.get("sumber", SUNEGG_URL),
                    "updated_at": item.get("updated_at", now_iso()),
                },
                "$setOnInsert": {
                    "created_at": item.get("created_at", now_iso()),
                },
            },
            upsert=True,
        )

        total_upsert += 1

    log(f"Data berhasil disimpan/update ke MongoDB: {total_upsert} record")

# =========================
# AMBIL DATA UNTUK REPORT
# =========================

def ambil_data_nasional(collection, limit=30):
    cursor = collection.find(
        {
            "wilayah": "Nasional",
            "harga": {
                "$ne": None,
            },
        }
    ).sort("tanggal", DESCENDING).limit(limit)

    data = list(cursor)
    data.reverse()

    return data


def ambil_data_regional_terbaru(collection):
    cursor = collection.find(
        {
            "wilayah": {
                "$ne": "Nasional",
            },
            "harga": {
                "$ne": None,
            },
        }
    ).sort("tanggal", DESCENDING)

    data_per_wilayah = {}

    for item in cursor:
        wilayah = item.get("wilayah", "")

        if wilayah and wilayah not in data_per_wilayah:
            data_per_wilayah[wilayah] = item

    return list(data_per_wilayah.values())


def ambil_harga_sebelumnya_wilayah(collection, wilayah, tanggal_terbaru):
    item = collection.find_one(
        {
            "wilayah": wilayah,
            "tanggal": {
                "$lt": tanggal_terbaru,
            },
            "harga": {
                "$ne": None,
            },
        },
        sort=[
            ("tanggal", DESCENDING),
        ],
    )

    if not item:
        return None

    return to_int(item.get("harga"))


def buat_summary(data_nasional):
    harga_list = [
        to_int(item.get("harga"))
        for item in data_nasional
        if to_int(item.get("harga")) > 0
    ]

    if not harga_list:
        return {
            "harga_terakhir": 0,
            "harga_sebelumnya": 0,
            "harga_rata_rata": 0,
            "harga_tertinggi_nasional": 0,
            "harga_terendah_nasional": 0,
            "persentase_kenaikan": 0,
            "indeks": 0,
            "volatilitas_pct": 0,
            "jumlah_data": 0,
        }

    harga_terakhir = harga_list[-1]
    harga_sebelumnya = harga_list[-2] if len(harga_list) >= 2 else harga_terakhir
    harga_awal = harga_list[0]

    harga_rata_rata = round(sum(harga_list) / len(harga_list))
    harga_tertinggi = max(harga_list)
    harga_terendah = min(harga_list)

    if harga_awal > 0:
        persentase_kenaikan = ((harga_terakhir - harga_awal) / harga_awal) * 100
    else:
        persentase_kenaikan = 0

    if harga_rata_rata > 0:
        indeks = (harga_terakhir / harga_rata_rata) * 100
    else:
        indeks = 0

    if harga_rata_rata > 0:
        volatilitas_pct = ((harga_tertinggi - harga_terendah) / harga_rata_rata) * 100
    else:
        volatilitas_pct = 0

    return {
        "harga_terakhir": harga_terakhir,
        "harga_sebelumnya": harga_sebelumnya,
        "harga_rata_rata": harga_rata_rata,
        "harga_tertinggi_nasional": harga_tertinggi,
        "harga_terendah_nasional": harga_terendah,
        "persentase_kenaikan": safe_round(persentase_kenaikan, 1),
        "indeks": safe_round(indeks, 2),
        "volatilitas_pct": safe_round(volatilitas_pct, 2),
        "jumlah_data": len(harga_list),
    }


def buat_trend(data_nasional):
    harga_list = [
        to_int(item.get("harga"))
        for item in data_nasional
        if to_int(item.get("harga")) > 0
    ]

    if not harga_list:
        return []

    min_harga = min(harga_list)
    max_harga = max(harga_list)

    trend = []

    for item in data_nasional:
        tanggal = str(item.get("tanggal", ""))
        harga = to_int(item.get("harga"))

        if not tanggal or harga <= 0:
            continue

        trend.append({
            "tanggal": tanggal,
            "label": format_label_tanggal(tanggal),
            "value": normalize_chart_value(harga, min_harga, max_harga),
            "harga_asli": harga,
        })

    return trend


def buat_harga_tertinggi(collection, data_regional):
    hasil = []

    for item in data_regional:
        tanggal = str(item.get("tanggal", ""))
        wilayah = str(item.get("wilayah", ""))
        harga = to_int(item.get("harga"))

        if not tanggal or not wilayah or harga <= 0:
            continue

        harga_sebelumnya = ambil_harga_sebelumnya_wilayah(
            collection,
            wilayah,
            tanggal,
        )

        if harga_sebelumnya is None:
            harga_sebelumnya = harga

        selisih = harga - harga_sebelumnya

        hasil.append({
            "tanggal": format_label_tanggal(tanggal),
            "wilayah": wilayah,
            "harga": harga,
            "harga_sebelumnya": harga_sebelumnya,
            "selisih": selisih,
        })

    hasil.sort(key=lambda x: x["harga"], reverse=True)

    return hasil

# =========================
# BUAT FILE JSON REPORT
# =========================

def buat_report_json(collection):
    data_nasional = ambil_data_nasional(collection, limit=30)
    data_regional = ambil_data_regional_terbaru(collection)

    summary = buat_summary(data_nasional)
    trend = buat_trend(data_nasional)
    harga_tertinggi = buat_harga_tertinggi(collection, data_regional)

    wilayah_options = ["Semua Wilayah"]

    for item in harga_tertinggi:
        wilayah = item.get("wilayah")

        if wilayah and wilayah not in wilayah_options:
            wilayah_options.append(wilayah)

    if len(wilayah_options) == 1:
        wilayah_options.extend(WILAYAH_DEFAULT)

    report_data = {
        "updated_at": now_iso(),
        "sumber": SUNEGG_URL,
        "satuan": "Rp/kg",
        "periode": f"{len(trend)} data terakhir",
        "wilayah_aktif": "Semua Wilayah",
        "summary": summary,
        "trend": trend,
        "harga_tertinggi": harga_tertinggi,
        "wilayah_options": wilayah_options,
    }

    response = {
        "success": True,
        "message": "Data report harga telur berhasil diperbarui",
        "code": 200,
        "data": report_data,
    }

    return response


def simpan_report_json(report):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )

    log(f"File report berhasil dibuat: {OUTPUT_FILE}")


# =========================
# MAIN
# =========================

def main():
    client = None

    try:
        client, collection = koneksi_mongodb()

        try:
            data_baru = scrape_indeks_harga()
            simpan_ke_mongodb(collection, data_baru)
        except Exception as scrape_error:
            log(f"Scraping gagal, lanjut pakai data terakhir MongoDB: {scrape_error}")

        report = buat_report_json(collection)

        simpan_report_json(report)

        log("Proses update report selesai")

    except Exception as error:
        log(f"ERROR: {error}")

        error_report = {
            "success": False,
            "message": str(error),
            "code": 500,
            "data": {
                "updated_at": now_iso(),
                "sumber": SUNEGG_URL,
                "satuan": "Rp/kg",
                "periode": "0 data",
                "wilayah_aktif": "Semua Wilayah",
                "summary": {
                    "harga_terakhir": 0,
                    "harga_sebelumnya": 0,
                    "harga_rata_rata": 0,
                    "harga_tertinggi_nasional": 0,
                    "harga_terendah_nasional": 0,
                    "persentase_kenaikan": 0,
                    "indeks": 0,
                    "volatilitas_pct": 0,
                    "jumlah_data": 0,
                },
                "trend": [],
                "harga_tertinggi": [],
                "wilayah_options": ["Semua Wilayah"],
            },
        }

        simpan_report_json(error_report)

        raise

    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
