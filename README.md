# LQ45 Recommender

**English:** A small Python tool that ranks **LQ45** (Indonesia Stock Exchange liquid index constituents) using public market data from **Yahoo Finance**. It outputs a composite **score** plus technical metrics (and optional fundamentals). Use it as a **screening aid**, not investment advice.

**Bahasa Indonesia:** Alat skrining saham **LQ45** berbasis data publik Yahoo Finance — skor gabungan, metrik harga, dan opsional PE/ROE/dividen. **Bukan saran investasi berizin**; hanya ringkasan kuantitatif untuk riset pribadi.

---

## Daftar isi

- [Fitur](#fitur)
- [Penyangkalan](#penyangkalan)
- [Persyaratan](#persyaratan)
- [Instalasi](#instalasi)
- [Penggunaan — CLI](#penggunaan--cli)
- [Penggunaan — antarmuka web (Streamlit)](#penggunaan--antarmuka-web-streamlit)
- [Cara kerja skor](#cara-kerja-skor)
- [Struktur proyek](#struktur-proyek)
- [API untuk pengembang](#api-untuk-pengembang)
- [Data & keterbatasan](#data--keterbatasan)
- [Memperbarui daftar LQ45](#memperbarui-daftar-lq45)
- [Deploy (mis. HP / internet)](#deploy-mis-hp--internet) — detail Streamlit Cloud: [DEPLOY.md](DEPLOY.md)
- [Dokumen terkait](#dokumen-terkait)

---

## Fitur

| | |
|---|---|
| **CLI** | Output tabel atau JSON; opsi `--top`, `--fundamentals`, `--period` |
| **Streamlit** | Dashboard: tema gelap default + toggle mode terang; status snapshot, tanggal penutupan terakhir di data, peringatan unduhan parsial, filter kode, mode top-N / semua LQ45, tampilan ringkas untuk layar kecil |
| **Skor** | 0–100 dari persentil lintas emiten (lihat [Cara kerja skor](#cara-kerja-skor)) |
| **Sumber data** | Harga & metrik via [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance) |

---

## Penyangkalan

- Program ini **bukan** produk investasi, **bukan** rekomendasi beli/jual, dan **bukan** nasihat keuangan berizin.
- Data dari pihak ketiga bisa **terlambat, tidak lengkap, atau salah** — verifikasi ke **emiten**, **IDX**, atau aplikasi sekuritas Anda sebelum keputusan.
- **Performa masa lalu** (momentum, return, dll.) **tidak menjamin** hasil ke depan.
- Pengguna bertanggung jawab atas keputusan dan risiko sendiri.

---

## Persyaratan

- Python **3.10+** (disarankan 3.11 atau 3.12)
- Koneksi internet untuk mengunduh data Yahoo Finance

---

## Instalasi

```bash
git clone https://github.com/YOUR_USERNAME/lq45-recommender.git
cd lq45-recommender

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Dependensi utama: `yfinance`, `pandas`, `numpy`, `streamlit`.

---

## Penggunaan — CLI

```bash
# 10 saham teratas (default periode harga 6 bulan)
python recommender.py --top 10

# Dengan fundamental (PE, ROE, dividen — lebih lambat)
python recommender.py --top 15 --fundamentals

# Output JSON (untuk skrip / integrasi)
python recommender.py --top 10 --fundamentals --json

# Periode unduhan harga (lihat dokumentasi yfinance: 1mo, 3mo, 6mo, 1y, ytd, max, …)
python recommender.py --top 10 --period 1y
```

**Argumen:**

| Argumen | Default | Keterangan |
|---------|---------|------------|
| `--top` | `10` | Jumlah baris teratas setelah diurut skor |
| `--fundamentals` | off | Ambil PE/ROE/dividen per ticker (banyak request) |
| `--period` | `6mo` | Periode historis harga untuk batch unduhan |
| `--json` | off | Keluaran JSON ke stdout |

---

## Penggunaan — antarmuka web (Streamlit)

```bash
source .venv/bin/activate
streamlit run streamlit_app.py
```

Buka browser di alamat yang ditampilkan (biasanya `http://localhost:8501`).

**Ringkasan opsi di sidebar:**

- **Mode gelap / terang:** toggle di bagian **Tampilan** (default gelap, selaras `.streamlit/config.toml`)
- **Tampilan baris:** Top N (urut skor) atau semua konstituen LQ45
- **Fundamental:** mengaktifkan kolom PE, ROE, yield dividen (lebih lambat)
- **Tampilan ringkas:** menyembunyikan beberapa kolom (nyaman di HP)
- **Periode data harga:** sama konsepnya dengan `--period` di CLI
- **Cari kode saham:** filter substring / beberapa kode
- **Refresh data:** mengosongkan cache singkat (TTL 2 menit) dan mengambil ulang data

---

## Cara kerja skor

Skor **0–100** adalah **peringkat relatif antar saham LQ45** pada satu snapshot, bukan nilai absolut “bagus/jelek”.

1. Untuk setiap metrik, nilai diubah menjadi **persentil** (0–100) di antara emiten yang datanya valid.
2. Persentil digabung dengan **bobot** (lihat `add_composite_score` di `recommender.py`):

   **Mode harga saja (default):**

   | Metrik | Bobot | Arah “lebih baik” |
   |--------|-------|-------------------|
   | Return ~1 bulan | 0.20 | Lebih tinggi |
   | Return ~3 bulan | 0.25 | Lebih tinggi |
   | Volatilitas tahunan | 0.15 | **Lebih rendah** |
   | Sharpe ~63 hari perdagangan | 0.20 | Lebih tinggi |

   **Jika fundamental aktif**, tiga komponen tambahan (masing-masing bobot nominal **0,10**): PE (lebih rendah), ROE (lebih tinggi), yield dividen (lebih tinggi). **Jumlah semua bobot** (teknikal + fundamental) lalu dipakai sebagai pembagi (`total_w` di kode), sehingga kontribusi tetap setara skala 0–100.

3. Metrik yang hilang untuk suatu saham diisi **50** pada bagian itu (netral) dalam perhitungan tertimbang — lihat implementasi untuk detail.

Untuk penjelasan kolom dalam bahasa sederhana, baca **[CARA-BACA-TABEL.md](CARA-BACA-TABEL.md)**.

---

## Struktur proyek

```
lq45-recommender/
├── README.md                 # Dokumen ini
├── DEPLOY.md                 # Panduan deploy Streamlit Community Cloud
├── CARA-BACA-TABEL.md        # Panduan membaca kolom (pemula)
├── requirements.txt
├── .streamlit/
│   └── config.toml           # Opsi Streamlit (lokal & cloud)
├── constituents.py           # Daftar kode LQ45 & simbol Yahoo (.JK)
├── recommender.py            # Pipeline: unduh → metrik → skor → CLI
└── streamlit_app.py          # Dashboard Streamlit
```

---

## API untuk pengembang

Modul `recommender` dapat diimpor dari skrip lain:

```python
from recommender import run, run_with_meta, RunResult

# Hanya DataFrame (diiris `top` baris pertama)
df = run(top=10, use_fundamentals=False, price_period="6mo")

# Seluruh baris LQ45 + metadata (unduhan parsial, tanggal bar terakhir)
result: RunResult = run_with_meta(use_fundamentals=True, price_period="6mo")
# result.table          # DataFrame penuh, sudah diurut skor
# result.failed_download_codes  # list kode yang gagal di batch harga
# result.price_last_date        # Timestamp tanggal bar terakhir di panel
```

---

## Data & keterbatasan

| Topik | Penjelasan singkat |
|-------|---------------------|
| **Sumber** | Yahoo Finance lewat `yfinance`; format ticker IDX: `KODE.JK` |
| **Harga** | Bukan kuotasi real-time; cocok untuk skrining, bukan eksekusi detik-per-detik |
| **Fundamental** | Field `info` Yahoo sering **perkiraan** atau tidak update — silang dengan laporan keuangan |
| **Indeks LQ45** | Daftar di `constituents.py` **manual**; harus diperbarui saat BEI rebalance |
| **Rate limit** | Terlalu sering refresh bisa dibatasi Yahoo — gunakan cache (Streamlit) atau jeda |

---

## Memperbarui daftar LQ45

1. Cek pengumuman resmi **BEI / IDX** (rebalancing indeks LQ45).
2. Edit `LQ45_CODES` di **`constituents.py`** (urutan bisa mengikuti daftar resmi).
3. Uji dengan `python recommender.py --top 5` dan pastikan tidak ada error massal.

---

## Deploy (mis. HP / internet)

**Streamlit Community Cloud (gratis, disarankan untuk app ini):** ikuti panduan langkah demi langkah di **[DEPLOY.md](DEPLOY.md)** (login GitHub → *New app* → branch `main` → main file **`streamlit_app.py`**).

Ringkas:

1. Push repositori ke **GitHub** (**publik** untuk tier gratis Streamlit).
2. Di [share.streamlit.io](https://share.streamlit.io), hubungkan repo, pilih **`streamlit_app.py`**, deploy.

Perhatikan batasan gratis (sleep saat idle, cold start, resource) dan bahwa **kode publik** terlihat semua orang. Alternatif: VPS, Render, Railway, atau jalankan di rumah + **Tailscale** / **Cloudflare Tunnel** (lebih teknis).

---

## Dokumen terkait

| File | Isi |
|------|-----|
| [CARA-BACA-TABEL.md](CARA-BACA-TABEL.md) | Arti tiap kolom untuk pemula |
| [DEPLOY.md](DEPLOY.md) | Deploy gratis ke Streamlit Community Cloud |

---

## Kontribusi

Issue dan pull request dipersilakan: perbaikan bug, pembaruan konstituen LQ45 setelah pengumuman resmi, atau dokumentasi. Harap jaga **penyangkalan** tetap jelas di UI dan README.

---

## Lisensi

Repositori ini tidak menyertakan file `LICENSE` secara default. Jika Anda melakukan fork untuk dipublikasikan, pertimbangkan menambahkan lisensi eksplisit (mis. MIT) sesuai keinginan Anda.
