def fetch_halaman(url: str):
    """Ambil dan parse HTML dari URL yang diberikan."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        print(f"Berhasil fetch: {url} [{response.status_code}]")
        return soup
    except requests.RequestException as e:
        print(f"Gagal fetch {url}: {e}")
        return None


def parse_angka(teks: str):
    """Ekstrak angka dari string seperti 'Rp 24.645/kg' → 24645.0"""
    if not teks:
        return None
    bersih = re.sub(r"[^\d,.]", "", teks).replace(".", "").replace(",", ".")
    try:
        return float(bersih )
    except ValueError:
        return None


def scrape_indeks_harga() -> dict:
    """
    Scrape data indeks harga telur dari sunegg.id.
    Mengembalikan dict berisi harga nasional, indeks, dan data regional.
    """
    soup = fetch_halaman(BASE_URL)
    if not soup:
        return {}

    data = {
        "tanggal"       : datetime.now().strftime("%Y-%m-%d"),
        "timestamp"     : datetime.now().isoformat(),
        "harga_nasional": None,
        "harga_tertinggi": None,
        "harga_terendah" : None,
        "harga_rata2"    : None,
        "volatilitas_pct": None,
        "indeks"         : None,
        "regional"       : {},
        "sumber"         : BASE_URL
    }

    teks_halaman = soup.get_text(separator=" ")

    # Ambil harga saat ini
    pola_saat_ini = re.search(r'Saat\s*Ini\s*Rp([\d.,]+)/kg', teks_halaman)
    if pola_saat_ini:
        data["harga_nasional"] = parse_angka(pola_saat_ini.group(1))

    # Fallback: cari Rp angka/kg
    if not data["harga_nasional"]:
        for el in soup.find_all(True):
            teks = el.get_text(strip=True)
            if "Rp" in teks and "/kg" in teks:
                angka = parse_angka(teks)
                if angka and 15000 < angka < 40000:
                    data["harga_nasional"] = angka
                    break

    # Ambil harga tertinggi, terendah, rata-rata
    pola_tertinggi = re.search(r'Tertinggi\s*Rp([\d.,]+)/kg', teks_halaman)
    pola_terendah  = re.search(r'Terendah\s*Rp([\d.,]+)/kg', teks_halaman)
    pola_rata2     = re.search(r'Rata-rata\s*Rp([\d.,]+)/kg', teks_halaman)
    pola_vol       = re.search(r'Volatilitas\s*([\d.]+)%', teks_halaman)

    if pola_tertinggi: data["harga_tertinggi"]  = parse_angka(pola_tertinggi.group(1))
    if pola_terendah:  data["harga_terendah"]   = parse_angka(pola_terendah.group(1))
    if pola_rata2:     data["harga_rata2"]       = parse_angka(pola_rata2.group(1))
    if pola_vol:       data["volatilitas_pct"]   = float(pola_vol.group(1))

    # Hitung indeks
    if data["harga_nasional"]:
        data["indeks"] = round((data["harga_nasional"] / HARGA_DASAR) * 100, 2)

    # Regional
    wilayah_map = {
        "Jabar-DKI"  : ["jabar", "dki", "jakarta", "jawa barat"],
        "Jawa Tengah": ["jateng", "jawa tengah"],
        "Jawa Timur" : ["jatim", "jawa timur"],
        "Luar Jawa"  : ["luar jawa", "sumatra", "kalimantan", "sulawesi"]
    }
    paragraf = teks_halaman.lower()
    for wilayah, kata_kunci in wilayah_map.items():
        for kunci in kata_kunci:
            pola = re.search(rf"{kunci}[^\n]*(\d{{2,3}}\.\d{{3}})", paragraf)
            if pola:
                data["regional"][wilayah] = parse_angka(pola.group(1))
                break

    print(f"\n Hasil Scraping ({data['tanggal']}):")
    print(f"   Harga Nasional : Rp {data['harga_nasional']:,.0f}/kg" if data['harga_nasional'] else "   Harga Nasional : -")
    print(f"   Tertinggi 30H  : Rp {data['harga_tertinggi']:,.0f}/kg" if data['harga_tertinggi'] else "   Tertinggi 30H  : -")
    print(f"   Terendah  30H  : Rp {data['harga_terendah']:,.0f}/kg" if data['harga_terendah'] else "   Terendah 30H   : -")
    print(f"   Rata-rata 30H  : Rp {data['harga_rata2']:,.0f}/kg" if data['harga_rata2'] else "   Rata-rata 30H  : -")
    print(f"   Volatilitas    : {data['volatilitas_pct']}%" if data['volatilitas_pct'] else "   Volatilitas     : -")
    print(f"   Indeks         : {data['indeks']}" if data['indeks'] else "   Indeks          : -")
    print(f"   Regional       : {data['regional']}")
    return data


def buat_histori_simulasi_30hari(data_hari_ini: dict) -> list:
    """
    Buat data historis 30 hari yang realistis berdasarkan data aktual hari ini.
    Digunakan saat MongoDB belum punya riwayat 30 hari.
    """
    harga_kini  = data_hari_ini.get("harga_nasional", HARGA_DASAR) or HARGA_DASAR
    tertinggi   = data_hari_ini.get("harga_tertinggi") or (harga_kini * 1.065)
    terendah    = data_hari_ini.get("harga_terendah")  or (harga_kini * 0.980)
    vol_pct     = (data_hari_ini.get("volatilitas_pct") or 6.5) / 100

    np.random.seed(42) #generator acak
    harga_list = []
    h = tertinggi  # mulai dari tertinggi 30 hari lalu, turun ke harga kini
    langkah = (tertinggi - harga_kini) / 29

    for i in range(30):
        noise  = np.random.normal(0, harga_kini * vol_pct * 0.15)
        harga  = round(max(terendah, min(tertinggi, h - langkah * i + noise)), 0)
        harga_list.append(harga)

    # Pastikan hari terakhir = harga aktual
    harga_list[-1] = harga_kini

    regional_base = data_hari_ini.get("regional", {})
    docs = []
    for i, h_val in enumerate(harga_list):
        tgl = (datetime.now() - timedelta(days=29 - i)).strftime("%Y-%m-%d")
        docs.append({
            "tanggal"        : tgl,
            "timestamp"      : tgl + "T00:00:00",
            "harga_nasional" : h_val,
            "indeks"         : round(h_val / HARGA_DASAR * 100, 2),
            "volatilitas_pct": data_hari_ini.get("volatilitas_pct"),
            "harga_tertinggi": tertinggi,
            "harga_terendah" : terendah,
            "harga_rata2"    : data_hari_ini.get("harga_rata2"),
            "regional"       : {
                k: round(v * h_val / harga_kini, 0) if v else None
                for k, v in regional_base.items()
            },
            "sumber"         : BASE_URL
        })
    return docs


# Jalankan scraping
data_hari_ini = scrape_indeks_harga()
