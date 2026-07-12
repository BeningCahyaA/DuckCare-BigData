import json
from datetime import datetime
from statistics import mean

INPUT_FILE = "data/harga_telur.json"
OUTPUT_FILE = "data/report_harga_telur.json"

def load_data():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_report(data):
    # Ambil semua harga
    harga = [item["harga"] for item in data if "harga" in item]

    if not harga:
        return {
            "status": "error",
            "message": "Tidak ada data harga"
        }

    report = {
        "status": "success",
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "summary": {
            "jumlah_data": len(harga),
            "harga_tertinggi": max(harga),
            "harga_terendah": min(harga),
            "harga_rata_rata": round(mean(harga), 2)
        },

        "chart": data
    }

    return report

def save_report(report):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

def main():
    data = load_data()
    report = generate_report(data)
    save_report(report)

    print("Report berhasil dibuat.")

if __name__ == "__main__":
    main()
