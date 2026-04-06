# Cara baca tabel skrining LQ45 (untuk pemula)

Program ini menampilkan **beberapa angka ringkas** per saham. Angka itu **bukan ramalan harga**, melainkan ringkasan dari data yang diunduh dari Yahoo Finance. Di bawah ini arti tiap kolom dengan bahasa sederhana.

---

## Kolom yang selalu ada

### `code`

**Kode saham** di Bursa Efek Indonesia, misalnya `BBCA`, `BBRI`. Satu kode = satu perusahaan tercatat.

---

### `score`

**Skor gabungan** dari 0 sampai 100 (makin tinggi = makin “di atas” dibanding saham LQ45 lain *menurut rumus program ini*).

- Bukan nilai “bagus buruk” mutlak, dan **bukan** saran beli/jual.
- Skor memadukan beberapa hal (momentum harga, volatilitas, dan kalau Anda pakai `--fundamentals` juga PE, ROE, dividen). Jadi saham yang skornya tinggi bisa jadi sedang **naik kencang** atau **relatif stabil** tergantung isi angka lainnya.

**Analogi sederhana:** seperti nilai ujian yang menggabungkan beberapa soal — bukan jaminan lulus, hanya ringkasan.

---

### `error`

Kalau ada teks di sini (bukan kosong/`None`), data untuk saham itu **kurang atau gagal diambil**. Baris itu sebaiknya **diabaikan** untuk perbandingan, atau dicek manual di aplikasi sekuritas / situs IDX.

---

### `last_price`

**Harga penutupan terakhir** yang kebaca dari data historis (dalam **rupiah per lembar**).

- Bukan harga real-time detik ini; bisa sedikit beda dengan harga di aplikasi Anda saat Anda buka.
- Harga saham **bukan** ukuran “murah/mahal” sendirian — perusahaan besar bisa punya harga per lembar kecil atau besar tergantung jumlah saham beredar.

---

### `ret_1m_pct`

**Perubahan harga sekitar 1 bulan terakhir**, dalam **persen**.

- Contoh: `5.0000` artinya kira-kira naik **5%** dari awal jendela 1 bulan itu.
- Angka **negatif** artinya dalam periode itu harga **turun**.

**Istilah:** *return* = hasil/laba-rugi dalam persen dalam suatu periode (di sini dari pergerakan harga, belum dipotong biaya jual-beli).

---

### `ret_3m_pct`

Sama seperti di atas, tapi untuk **sekitar 3 bulan terakhir**.

- Dipakai untuk melihat apakah tren harga **lebih panjang** masih positif atau tidak.

---

### `vol_ann_pct`

**Volatilitas** perkiraan **setahun** (diannualisasi), dalam **persen**, berdasarkan fluktuasi harga harian.

- Angka **lebih besar** = harga **lebih “loncat-loncat”** (naik turun besar dalam waktu singkat).
- Angka **lebih kecil** = pergerakan relatif **lebih tenang**.

Di skor program, volatilitas **rendah** sedikit diutamakan (lebih “stabil” menurut rumus ini). Itu **tidak** berarti saham volatil pasti buruk — banyak trader justru mencari volatilitas.

---

### `sharpe_63d`

**Sharpe ratio** perkiraan dari **sekitar 63 hari perdagangan terakhir** (kira-kira 3 bulan).

- Secara kasar: membandingkan **imbal hasil rata-rata harian** dengan **“kebisingan”/risiko** (simpangan) harian.
- **Lebih tinggi** = dalam rumus ini, imbal relatif lebih besar dibanding fluktuasinya (versi sederhana; bukan Sharpe resmi portofolio Anda).

Angka ini bisa **negatif** kalau return rata-rata harian buruk dibanding volatilitasnya.

---

## Kolom tambahan jika Anda pakai `--fundamentals`

### `trailing_pe`

**Trailing P/E (price-to-earnings)** = harga dibanding **laba per saham** dari kinerja **yang sudah terjadi** (biasanya laba 12 bulan terakhir).

- **Lebih kecil** (dengan asumsi laba positif) sering dibilang lebih “murah” dibanding labanya — tapi **tidak otomatis** lebih baik (bisa juga labanya turun atau datanya tidak cocok).
- Kalau kosong (`NaN`), Yahoo tidak punya data yang dipakai program.

---

### `forward_pe`

**Forward P/E** memakai **perkiraan laba ke depan** (kalau tersedia di sumber data).

- Sama-sama ringkas “seberapa mahal harga dibanding laba”, tapi pakai **proyeksi**.
- Data bisa **salah atau tidak update**; jangan dianggap pasti.

---

### `roe`

**Return on equity** — laba dibanding **modal pemegang saham** (ekuitas), biasanya dalam **desimal**.

- Contoh: `0.15` artinya kira-kira **15%** ROE (tergantung definisi persis di laporan).
- **Lebih tinggi** sering diartikan perusahaan lebih efisien menghasilkan laba dari modal sendiri — tetap perlu dibaca bersama utang, industri, dan tren.

---

### `debt_to_equity` (di UI: **Utang / ekuitas**)

**Debt-to-equity** dari Yahoo: perbandingan **total utang** dengan **ekuitas pemegang saham**.

- Angka **lebih tinggi** berarti utang relatif lebih besar dibanding modal sendiri (leverage lebih tinggi). Apakah “sehat” tergantung **industri** dan kebijakan perusahaan.
- Di **Streamlit**, kolom ini pakai label singkat **Utang / ekuitas**; angka dari Yahoo bisa berbeda definisi dengan laporan IDX — silang dengan laporan keuangan jika putuskan investasi.

---

### `market_cap` / **Kap. pasar (Mrd Rp)** di UI

**Kapitalisasi pasar** = perkiraan nilai seluruh saham beredar di pasar (harga × jumlah saham), dari Yahoo.

- Di **Streamlit**, ditampilkan dalam **miliar rupiah** (kolom **Kap. pasar (Mrd Rp)**) agar lebih mudah dibaca daripada angka penuh.
- Di **CLI / JSON** mentah mungkin masih bernama `market_cap` dalam rupiah penuh — sama artinya, beda format.

---

### `div_pct`

**Perkiraan yield dividen tahunan dalam persen** (dari data Yahoo, sudah dibantu dinormalisasi program).

- Arti kasar: kalau dividen seperti itu dan harga seperti itu, sekitar **berapa persen** tahunan dari harga — **bukan jaminan** dividen tahun depan sama.
- Perusahaan bisa **mengurangi, menunda, atau tidak** membagikan dividen.

---

## Ringkasan untuk pemula

1. **Baca tabel sebagai “cek kilat statistik”, bukan saran investasi.**
2. **Momentum** (`ret_1m_pct`, `ret_3m_pct`) = harga baru-baru ini naik atau turun.
3. **Volatilitas** = seberapa “gelisah” harganya.
4. **PE & ROE** = cuplikan valuasi dan efisiensi laba; wajib **diverifikasi** dari laporan keuangan resmi kalau Anda serius.
5. Keputusan beli/jual sebaiknya melibatkan **tujuan Anda**, **horizon waktu**, dan kalau perlu **orang berizin** (penasihat keuangan/analis).

---

## Perintah yang menghasilkan tabel ini

```bash
source .venv/bin/activate
python recommender.py --top 10
python recommender.py --top 10 --fundamentals
```

Output `--json` berisi kolom yang sama (lebih cocok untuk diproses aplikasi lain).

---

*Dokumen ini menjelaskan tampilan program; bukan dokumen hukum atau penawaran efek.*
