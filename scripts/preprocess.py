def baca_dari_mongodb(client, hari: int = 30) -> pd.DataFrame:
    """
    Baca data N hari terakhir dari MongoDB dan konversi ke DataFrame.
    """
    if not client:
        return pd.DataFrame()
    col   = client[DB_NAME][COL_NAME]
    batas = (datetime.now() - timedelta(days=hari)).strftime("%Y-%m-%d")
    cursor = col.find(
        {"tanggal": {"$gte": batas}}, #greater than or equal
        {"_id": 0, "tanggal": 1, "harga_nasional": 1,
         "indeks": 1, "volatilitas_pct": 1, "regional": 1}
    ).sort("tanggal", 1)
    df = pd.DataFrame(list(cursor))
    print(f"Berhasil membaca {len(df)} dokumen dari MongoDB ({hari} hari terakhir)")
    return df


def preprocessing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pipeline preprocessing lengkap:
    - Parse tanggal
    - Handle missing values
    - Expand kolom regional
    - Feature engineering
    """
    if df.empty:
        print("DataFrame kosong, skip preprocessing.")
        return df
    #parse tanggal
    df["tanggal"] = pd.to_datetime(df["tanggal"]) #string ke datatime
    df = df.sort_values("tanggal").reset_index(drop=True)
    #konversi tipe data
    df["harga_nasional"] = pd.to_numeric(df["harga_nasional"], errors="coerce") #"errors="coerce" -> Nan
    df["indeks"]         = pd.to_numeric(df["indeks"],         errors="coerce")

    #Expand Kolom Regional
    if "regional" in df.columns:
        regional_df = pd.json_normalize(df["regional"].fillna({}))
        regional_df.columns = [f"harga_{k.lower().replace('-','_').replace(' ','_')}"
                                for k in regional_df.columns]
        df = pd.concat([df.drop(columns=["regional"]), regional_df], axis=1)

    #Handle missing value
    kolom_harga = [c for c in df.columns if c.startswith("harga_")]
    df[kolom_harga] = df[kolom_harga].ffill().bfill() #forward & backword

    if df["indeks"].isna().any():
        df["indeks"] = (df["harga_nasional"] / HARGA_DASAR * 100).round(2)

    #Feature Engineering
    df["pct_change_harian"] = df["harga_nasional"].pct_change() * 100
    df["pct_change_harian"] = df["pct_change_harian"].round(3)
    df["ma7"]  = df["harga_nasional"].rolling(window=7,  min_periods=1).mean().round(0)
    df["ma30"] = df["harga_nasional"].rolling(window=30, min_periods=1).mean().round(0)

    mean_h = df["harga_nasional"].mean()
    std_h  = df["harga_nasional"].std()
    if std_h and std_h > 0:
        df["zscore"]  = ((df["harga_nasional"] - mean_h) / std_h).round(3) #harga dari rata-rata dalam satuan deviasi
    else:
        df["zscore"]  = 0.0
    df["anomali"]      = df["zscore"].abs() > 2
    df["volatilitas_7d"] = (
        df["pct_change_harian"].rolling(7, min_periods=2).std().round(3)
    )

    print(f"Preprocessing selesai. Shape: {df.shape}")
    print(f"   Kolom: {list(df.columns)}")
    return df


# Baca 30 hari dari MongoDB
df_raw = baca_dari_mongodb(mongo_client, hari=30)
df     = preprocessing(df_raw)

# Fallback jika MongoDB masih kosong
if df.empty:
    print("\nMongoDB kosong — menggunakan data simulasi 30 hari...")
    if data_hari_ini:
        docs_sim = buat_histori_simulasi_30hari(data_hari_ini)
    else:
        # Data dummy jika scraping juga gagal
        docs_sim = buat_histori_simulasi_30hari({
            "harga_nasional": HARGA_DASAR,
            "harga_tertinggi": 26255,
            "harga_terendah" : 24645,
            "harga_rata2"    : 25390,
            "volatilitas_pct": 6.5,
            "regional"       : {"Jabar-DKI": 25000, "Jawa Tengah": 24000,
                                "Jawa Timur": 24300, "Luar Jawa": 25800}
        })
    df_raw = pd.DataFrame(docs_sim)
    df     = preprocessing(df_raw)
    print(f"Data simulasi 30 hari: {df.shape}")
