# Deploy ke Streamlit Community Cloud (gratis)

Panduan ini untuk menjalankan **LQ45 Recommender** di [Streamlit Community Cloud](https://streamlit.io/cloud) agar bisa dibuka dari browser (termasuk HP) tanpa menjalankan laptop.

## Prasyarat

1. **Akun GitHub** yang punya akses push ke repo proyek ini (mis. `abifdhllh/lq45-recommender`).
2. Repo **publik** — tier gratis Streamlit Community biasanya **hanya untuk repositori publik**.
3. Kode sudah **ter-push** ke GitHub (branch `main` atau `master`).

## Isi repo yang dipakai Cloud

| File / folder | Fungsi |
|---------------|--------|
| `streamlit_app.py` | Entry point aplikasi web |
| `recommender.py`, `constituents.py` | Logika skrining |
| `requirements.txt` | Dependensi Python (wajib di root) |
| `.streamlit/config.toml` | Opsi browser/tema (opsional) |

Tidak perlu `secrets` — aplikasi hanya memanggil Yahoo Finance lewat internet.

## Langkah deploy

### 1. Push ke GitHub

```bash
git add .
git commit -m "Siap deploy Streamlit"
git push origin main
```

Pastikan remote benar (SSH/HTTPS ke repo Anda).

### 2. Buka Streamlit Community Cloud

1. Kunjungi **[share.streamlit.io](https://share.streamlit.io)** (atau dari [streamlit.io/cloud](https://streamlit.io/cloud) → **Sign in**).
2. Login dengan **GitHub** dan **izinkan** Streamlit mengakses repositori (setidaknya repo ini).

### 3. Buat aplikasi baru

1. Klik **New app** (atau **Create app**).
2. **Repository:** pilih `username/lq45-recommender` (ganti dengan akun & nama repo Anda).
3. **Branch:** biasanya `main`.
4. **Main file path:** `streamlit_app.py`  
   (harus persis — huruf besar/kecil sama dengan di repo).
5. Klik **Deploy**.

### 4. Tunggu build

- Cloud akan menginstal paket dari `requirements.txt` lalu menjalankan `streamlit run streamlit_app.py`.
- Build pertama bisa **beberapa menit**. Jika gagal, buka **Logs** di dashboard Streamlit untuk pesan error (mis. dependensi tidak terpasang).

### 5. Python version (jika error build)

Di halaman **Settings** aplikasi di Streamlit Cloud:

- **Python version:** pilih **3.11** atau **3.12** (disarankan) jika ada masalah kompatibilitas.

### 6. URL aplikasi

Setelah sukses, Anda mendapat URL seperti:

`https://lq45-recommender-username.streamlit.app`

(nama pasti mengikuti aturan Streamlit — tercantum di dashboard).

Bookmark URL ini di HP; tampilan sudah mendukung scroll horizontal & mode ringkas di sidebar.

## Setelah deploy

- **Update kode:** push ke GitHub → Streamlit biasanya **redeploy otomatis** (atau tombol **Reboot** / **Manage app** di dashboard).
- **Sleep / cold start:** tier gratis bisa **mematikan** app saat tidak dipakai; akses pertama bisa **lambat** beberapa detik sampai “bangun”.
- **Rate limit Yahoo:** banyak pengguna atau refresh sangat sering bisa membuat unduhan data gagal — itu batas sumber data, bukan bug Streamlit.

## Masalah umum

| Gejala | Yang dicek |
|--------|------------|
| Build gagal | Log di Cloud; pastikan `requirements.txt` lengkap dan `streamlit_app.py` ada di path yang dipilih. |
| Halaman putih / error | Buka **Logs**; cek apakah `recommender` / `constituents` ikut ter-push. |
| Permission GitHub | Di GitHub → **Settings** → **Applications** → pastikan Streamlit punya akses ke repo/org. |

## Privasi & keamanan

- Repo **publik** berarti **siapa saja** bisa melihat kode di GitHub.
- Jangan menaruh **API key / password** di kode; aplikasi ini tidak memerlukannya.

Untuk penjelasan umum deploy lain (VPS, tunnel), lihat juga bagian **Deploy** di [README.md](README.md).
