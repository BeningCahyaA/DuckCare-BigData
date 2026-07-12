import os
import json
import pandas as pd

CSV_PATH = "data/harga_telur.csv"

df = pd.read_csv(CSV_PATH)

df["tanggal"] = pd.to_datetime(df["tanggal"])

df = df.sort_values("tanggal")

# ------------------------
# SUMMARY
# ------------------------

harga_terakhir = int(df.iloc[-1]["harga_nasional"])

harga_sebelumnya = int(df.iloc[-2]["harga_nasional"])

harga_tertinggi = int(df["harga_nasional"].max())

harga_terendah = int(df["harga_nasional"].min())

harga_rata = int(df["harga_nasional"].mean())

persen = round(
    ((harga_terakhir-harga_sebelumnya)/harga_sebelumnya)*100,
    2
)

# ------------------------
# TREND
# ------------------------

min_harga = df["harga_nasional"].min()
max_harga = df["harga_nasional"].max()

trend=[]

for _,row in df.iterrows():

    if max_harga==min_harga:
        value=0.5
    else:
        value=(row["harga_nasional"]-min_harga)/(max_harga-min_harga)

    trend.append({

        "label":row["tanggal"].strftime("%d/%m"),

        "value":round(float(value),3),

        "harga_asli":int(row["harga_nasional"])

    })

# ------------------------
# HARGA TERTINGGI
# ------------------------

harga=[]

for _,row in df.iterrows():

    harga.append({

        "tanggal":row["tanggal"].strftime("%Y-%m-%d"),

        "wilayah":"Nasional",

        "harga":int(row["harga_nasional"]),

        "harga_sebelumnya":int(harga_sebelumnya)

    })

# ------------------------

report={

    "summary":{

        "harga_terakhir":harga_terakhir,

        "harga_sebelumnya":harga_sebelumnya,

        "harga_tertinggi_nasional":harga_tertinggi,

        "harga_terendah_nasional":harga_terendah,

        "harga_rata_rata":harga_rata,

        "persentase_kenaikan":persen,

        "jumlah_data":len(df),

        "indeks":float(df.iloc[-1]["indeks"]),

        "volatilitas_pct":0

    },

    "trend":trend,

    "harga_tertinggi":harga,

    "wilayah_options":[
        "Nasional"
    ],

    "updated_at":df.iloc[-1]["tanggal"].strftime("%Y-%m-%d"),

    "sumber":"DuckCare BigData",

    "satuan":"Rp/kg"

}

os.makedirs("output",exist_ok=True)

with open(
    "output/report_harga_telur.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        report,
        f,
        indent=4,
        ensure_ascii=False
    )

print("report_harga_telur.json berhasil dibuat")
