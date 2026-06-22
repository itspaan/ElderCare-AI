# Catatan Progres — ElderCare AI

Catatan progres dengan bahasa sehari-hari, terbaru di atas. Cukup baca bagian
atas untuk ingat sampai mana terakhir kita kerjakan. Setiap entri berisi **apa
yang berubah**, **kenapa**, dan **cara mengeceknya**. Untuk checklist status
lebih lengkap lihat [CLAUDE.md](../CLAUDE.md); untuk rencana pengumpulan data
lihat [DATA_COLLECTION.md](DATA_COLLECTION.md).

> Cara pakai: setiap kali selesai satu bagian pekerjaan, tambahkan entri baru
> bertanggal di paling atas. Singkat saja — beberapa poin per entri. **Setiap
> entri WAJIB punya bagian "Langkah selanjutnya"**, dan setelahnya perbarui juga
> daftar "🎯 Langkah Selanjutnya" di bawah ini supaya selalu tahu arah.
>
> Catatan: file ini sengaja ditulis dalam Bahasa Indonesia supaya mudah dibaca.
> File lain di proyek ini tetap Bahasa Inggris.

---

## 🎯 Langkah Selanjutnya (daftar hidup — terbaru selalu di sini)

Urut dari yang paling penting untuk skripsi. Centang kalau sudah, lalu pindahkan
ringkasannya jadi entri bertanggal di bawah.

**Prioritas 1 — Jalur data nyata (kontribusi utama skripsi):**
- [ ] Urus persetujuan **IRB / etik** dari kampus sebelum ambil data peserta.
- [ ] Siapkan **database persisten** (managed Postgres, mis. Supabase/Render)
      untuk ganti SQLite lokal — biar data tidak hilang saat redeploy.
- [ ] **Uji coba (pilot)** isi beberapa data lewat form survey, lalu pastikan
      datanya tetap ada setelah app di-restart/redeploy.
- [ ] **Kumpulkan** data berlabel — target beberapa lusin per kelas, seimbang
      antar 5 kondisi (lihat DATA_COLLECTION.md §5).
- [ ] **Export → retrain → evaluasi**: unduh CSV survey, latih ulang model,
      laporkan akurasi/precision/recall/F1 per kelas + confusion matrix
      (harusnya jauh di bawah 100% — itu wajar dan justru bagus untuk dibahas).
- [ ] **Bandingkan** model sintetis vs model data nyata — ini bagian hasil yang
      kuat untuk skripsi.

**Prioritas 2 — Penguat (kalau jalur data sudah jalan):**
- [ ] Sambungkan `training/train_model.py` agar bisa baca CSV survey (gabung
      data nyata + sintetis dengan penanda `source` untuk analisis).
- [ ] Tampilkan faktor explainability secara visual di dashboard UI.

**Prioritas 3 — Pengembangan lanjut (opsional / kalau ada waktu):**
- [ ] Tambah kondisi / fitur yang lebih kaya.
- [ ] Perluas bahasa (Hokkien/Hakka Taiwan) di atas EN + zh-TW.
- [ ] Suara asli (TTS/STT) dan telepon darurat sungguhan.

---

## 2026-06-21 — Survey riset (pengumpulan data nyata)

**Apa:** Menambahkan sisi survey supaya bisa mengumpulkan data nyata berlabel
dari lansia/pendamping, untuk akhirnya menggantikan dataset sintetis.

- File baru `tools/survey.py` (meniru gaya `tools/reminders.py`): penyimpanan
  SQLite di `storage/survey.db`, salinan JSON real-time, dan ekspor CSV.
  - Menyimpan baris **hanya jika consent bernilai true**.
  - Memvalidasi kondisi diagnosis terhadap 5 kelas model, jadi tebakan aplikasi
    sendiri tidak akan pernah menjadi label training.
  - Mencatat sumber label (clinician / medical_record / self_report) dan memakai
    `participant_id` acak (tanpa nama).
- Route API baru di `main.py`:
  - `POST /api/survey` — kirim satu data (mengembalikan 400 jika consent kosong
    atau field tidak valid).
  - `GET /api/survey/stats` — jumlah total + rincian per kondisi.
  - `GET /api/survey/export` — unduh CSV yang kolomnya sama persis dengan
    `data/elderly_synthetic_data.csv`, jadi `train_model.py` bisa langsung baca.
- Modal survey dwibahasa (EN / zh-TW) baru di `static/index.html`: tombol "Join
  the Research Survey" → kotak consent (checkbox wajib mengunci tombol Submit) →
  form → penghitung jumlah respons + umpan balik sukses/gagal.
- Memperbarui `DATA_COLLECTION.md` §7 dan roadmap/struktur/route di CLAUDE.md.

**Kenapa:** Model saat ini akurasinya ~100% hanya karena data sintetis terpisah
sempurna; data nyata berlabel adalah kontribusi empiris utama skripsi.

**Cara cek:**
```powershell
python -m uvicorn main:app --reload --port 8000
```
Buka http://127.0.0.1:8000 → "Join the Research Survey", coba submit dengan dan
tanpa consent, ganti bahasa EN/中文, lalu unduh `GET /api/survey/export` dan
pastikan header CSV-nya sama dengan `data/elderly_synthetic_data.csv`.

**Langkah selanjutnya:**
- Urus persetujuan IRB / etik sebelum mengumpulkan data dari peserta nyata.
- Ganti SQLite lokal dengan database persisten (managed Postgres) — disk free
  tier itu sementara/hilang saat redeploy (lihat DEPLOYMENT.md §6).
- Setelah ada data: export CSV → retrain → evaluasi jujur per kelas →
  bandingkan dengan model sintetis.

---

## Milestone sebelumnya (diisi ulang dari riwayat git)

Ini terjadi sebelum catatan ini dibuat; diringkas dari commit dan checklist
status.

- **Dokumentasi** — menambahkan MODEL_CARD, ARCHITECTURE, DEPLOYMENT, dan
  rencana DATA_COLLECTION; memindahkan PRD ke `docs/`.
- **Explainability** — `predict_disease_from_vitals` sekarang mengembalikan
  faktor utama yang mendorong tiap prediksi (perturbasi terhadap baseline
  klinis), dan agen menjelaskannya lewat kata-kata.
- **UI dwibahasa** — pengalih Inggris / Mandarin Tradisional (zh-TW) sekali tap,
  prompt awal yang dilokalkan, serta TTS/STT zh-TW. Menyelaraskan README,
  CLAUDE.md, dan PRD ke fokus Taiwan.
- **Aplikasi inti** — backend FastAPI (`main.py`) dengan endpoint chat /
  reminders / images; agen Gemini dengan function calling (`core/agent.py`);
  model screening Random Forest (`training/train_model.py`,
  `models/disease_model.pkl`) yang dilatih pada dataset sintetis
  (`data/generate_dummy.py`); reminders (SQLite + JSON), unggah/analisis gambar,
  panggilan darurat (simulasi), dan UI web dashboard + chat.
