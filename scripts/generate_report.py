import json
import os
from datetime import datetime

report = {
    "success": True,
    "data": {
        "summary": {
            "hargaTerakhir": 22145,
            "hargaSebelumnya": 22000,
            "hargaRataRata": 22100,
            "hargaTertinggiNasional": 25000,
            "hargaTerendahNasional": 21000,
            "persentaseKenaikan": 0.66,
            "indeks": 90.38,
            "volatilitasPct": 2.5,
            "jumlahData": 30
        },
        "trend": [
            {
                "label": "01/07",
                "value": 0.40,
                "hargaAsli": 21900
            },
            {
                "label": "02/07",
                "value": 0.55,
                "hargaAsli": 22050
            },
            {
                "label": "03/07",
                "value": 0.70,
                "hargaAsli": 22145
            }
        ],
        "hargaTertinggi": [
            {
                "tanggal": "2026-07-03",
                "wilayah": "Jabar-DKI",
                "harga": 25000,
                "hargaSebelumnya": 24800
            },
            {
                "tanggal": "2026-07-03",
                "wilayah": "Jawa Tengah",
                "harga": 24500,
                "hargaSebelumnya": 24400
            }
        ],
        "wilayahOptions": [
            "Jabar-DKI",
            "Jawa Tengah",
            "Jawa Timur",
            "Luar Jawa"
        ],
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sumber": "GitHub Actions",
        "satuan": "Rp/kg"
    }
}

os.makedirs("output", exist_ok=True)

with open("output/report_harga_telur.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=4)

print("report_harga_telur.json berhasil dibuat")
