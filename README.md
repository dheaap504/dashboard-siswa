# Dashboard Faktor Performa Siswa

Dashboard interaktif (Streamlit + Plotly) dari dataset *Student Performance Factors*
(6.607 siswa, 20 kolom). Gratis untuk dikembangkan dan diakses.

## Struktur proyek

```
dashboard-siswa/
├── app.py                         # Layout (sidebar menu, breadcrumb, filter popover), KPI, 5 halaman, pop-up detail
├── assets/style.css               # Tema visual (gaya Soft UI: kartu lembut, ikon gradien, kartu gelap)
├── src/
│   ├── data_loader.py             # Ambil data: csv | gsheet | supabase + cache TTL + cleaning
│   ├── analysis.py                # Statistik: pengaruh faktor, profil kelompok, insight otomatis
│   └── charts.py                  # Grafik Plotly (tiap titik membawa customdata untuk klik)
├── data/StudentPerformanceFactors.csv
├── supabase/schema.sql            # Tabel Postgres untuk mode real-time
├── scripts/upload_to_supabase.py  # Upload CSV awal ke Supabase (sekali jalan)
├── .streamlit/config.toml         # Tema
├── .streamlit/secrets.toml.example
└── requirements.txt
```

## Struktur visualisasi

| Bagian | Isi | Klik → pop-up |
|---|---|---|
| **KPI** | Jumlah siswa, rata-rata nilai, % ≥70, kehadiran, jam belajar (dengan selisih vs semua data saat difilter) | – |
| **Filter** (tombol Filter di kanan atas) | Jenis sekolah, gender, pendapatan, motivasi, rentang jam belajar & kehadiran | – |
| **Ringkasan** | Sebaran nilai · Temuan utama (dihitung ulang otomatis) · Peringkat pengaruh 19 faktor | Batang nilai → profil siswa bernilai itu · Batang faktor → detail faktor |
| **Eksplorasi faktor** | Pilih kelompok (Akademik / Keluarga & Lingkungan / Personal) → pilih faktor → rata-rata + interval kepercayaan 95% | Titik → profil kelompok (KPI, distribusi vs semua, profil numerik, ciri menonjol, daftar siswa) |
| **Kombinasi faktor** | Heatmap dua faktor numerik pilihan | Sel → profil irisan kelompok |
| **Profil siswa** | Scatter seluruh siswa + cari ID | Titik → profil individu (persentil, faktor pendukung/penghambat, semua atribut) |
| **Data** | Tabel lengkap + unduh CSV | Baris → profil siswa |

### Insight dari data
1. **Kehadiran adalah faktor terkuat** (r = 0,58): hadir 91–100% → rata-rata 70,2 vs 60–70% → 64,3.
2. **Jam belajar** kedua (r = 0,45): >30 jam/minggu → 71,0 vs ≤10 jam → 64,0.
3. Kombinasi keduanya (heatmap) memberi rentang nilai paling lebar.
4. **Les privat** membantu bertahap: 0 sesi → 66,5; 4 sesi → 68,2.
5. Faktor keluarga/lingkungan masing-masing hanya ±1–2 poin (keterlibatan ortu, akses sumber belajar paling besar).
6. **Jam tidur, gender, jenis sekolah ≈ tidak berpengaruh** (selisih <0,5 poin).
7. Nilai sangat terpusat (median 67) — hanya ~25% siswa mencapai ≥70.

Catatan data: 1 baris nilai 101 dipotong jadi 100; nilai kosong (Teacher_Quality 78,
Parental_Education_Level 90, Distance_from_Home 67) ditandai "Tidak diketahui".

## Jalankan lokal

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy gratis — Streamlit Community Cloud

1. Buat repo **GitHub** (boleh publik) dan push folder ini.
2. Buka **share.streamlit.io** → login pakai GitHub → **Create app**.
3. Pilih repo, branch `main`, file `app.py` → **Deploy**.
4. Dapat URL `https://nama-app.streamlit.app` yang bisa diakses siapa saja, gratis.
5. Setiap `git push` → app otomatis ter-update.

Catatan: app gratis "tidur" bila tidak dibuka beberapa hari; pengunjung pertama
cukup klik tombol bangunkan (~30 detik).

Alternatif gratis lain: **Hugging Face Spaces** (SDK Streamlit) atau **Render** (free web service).

## Mode real-time

Dashboard tidak perlu diubah — cukup ganti sumber data lewat **Secrets**
(di Streamlit Cloud: *App → Settings → Secrets*, isi seperti `secrets.toml.example`).

```
[Input data]  ──►  [Database/Sheet]  ──►  [Dashboard Streamlit]
 Google Form       Google Sheets           cache TTL 60 dtk
 / aplikasi        atau Supabase           + auto-refresh 30 dtk
```

### Opsi B — Google Sheets (paling mudah, tanpa kode)
1. Impor CSV ke Google Sheets (header kolom harus sama).
2. Data baru masuk lewat **Google Form** yang terhubung ke sheet itu, atau diketik langsung.
3. *File → Share → Publish to web* → pilih sheet → **CSV** → salin URL.
4. Secrets:
   ```toml
   DATA_SOURCE = "gsheet"
   GSHEET_CSV_URL = "https://docs.google.com/.../pub?output=csv"
   CACHE_TTL_SECONDS = 60
   AUTO_REFRESH_SECONDS = 60
   ```
Kekurangan: CSV publik Google di-cache ±5 menit, dan data bisa dilihat siapa pun yang punya URL.

### Opsi C — Supabase (benar-benar real-time, lebih aman)
1. Daftar **supabase.com** (free tier: 500 MB database) → buat project.
2. *SQL Editor* → jalankan `supabase/schema.sql`.
3. Upload data awal:
   ```bash
   SUPABASE_URL=https://xxx.supabase.co SUPABASE_SERVICE_KEY=... \
   python scripts/upload_to_supabase.py data/StudentPerformanceFactors.csv
   ```
4. Secrets (pakai **anon key**, bukan service key):
   ```toml
   DATA_SOURCE = "supabase"
   SUPABASE_URL = "https://xxx.supabase.co"
   SUPABASE_ANON_KEY = "eyJ..."
   CACHE_TTL_SECONDS = 30
   AUTO_REFRESH_SECONDS = 30
   ```
5. Data baru bisa masuk dari: Table Editor Supabase, aplikasi/form Anda via REST API,
   atau otomasi (n8n / Make / Zapier free tier).

Catatan: project Supabase gratis di-*pause* bila 7 hari tidak ada aktivitas —
cukup klik *Restore* di dashboard Supabase.

## Biaya
| Komponen | Layanan | Biaya |
|---|---|---|
| Kode | GitHub | Gratis |
| Hosting dashboard | Streamlit Community Cloud | Gratis |
| Database real-time | Google Sheets / Supabase free tier | Gratis |
| Akses pengguna | Browser, tanpa login | Gratis |

## Desain
Gaya visual terinspirasi template *Soft UI Dashboard* (Creative Tim, lisensi MIT): latar #f8f9fa, kartu putih radius 1rem dengan bayangan lembut, ikon bergradasi fuchsia, kartu grafik gelap, font Open Sans. Semua gaya ada di `assets/style.css`; warna grafik di `src/charts.py`.
