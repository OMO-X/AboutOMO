# Arsitektur Pure Cast / Android Auto HUD Cockpit (960x360)

Dokumen ini menjelaskan arsitektur tampilan navigasi independen (**Pure Cast / Android Auto Cockpit**) pada motor listrik OMOWAY tanpa melakukan rekam layar smartphone (*screen mirroring*).

---

## 1. Konsep Pure Cast vs Screen Mirroring

| Fitur | Screen Mirroring Biasa | Pure Cast Android Auto HUD (UMOX) |
| :--- | :--- | :--- |
| **Izin Sistem** | Perlu izin rekam layar (`MediaProjection`) dengan dialog konfirmasi Android | **Tanpa izin rekam layar**, langsung jalan instan via `ConnectedDevice` service |
| **Tampilan HP** | Layar HP terkunci / harus tetap menyala dan menampilkan maps | **Layar HP bebas**, bisa dimatikan atau dipakai untuk aplikasi lain |
| **Rasio Tampilan** | Sering gepeng / hitam di pinggir karena rasio HP (20:9) beda dengan speedometer (8:3) | **Native 960x360** (Full-screen pas tanpa distorsi atau pilar hitam) |
| **Informasi Layar** | Notifikasi WA, telepon, dan UI HP ikut terlihat di speedometer motor | **Khusus Navigasi & Cockpit Motor**: Speedometer, Baterai, Turn-by-Turn, Jam |

---

## 2. Arsitektur Rendering Surface

UMOX memanfaatkan input surface encoder perangkat keras Android (`MediaCodec.createInputSurface()`). 

```text
[HudDashboardRenderer (30 FPS)] 
          │ (Hardware-accelerated Canvas)
          ▼
   [Encoder InputSurface]
          │ (H.264 Hardware Codec @ 2 Mbps CBR)
          ▼
   [Desay SV 8-Byte Framing (Ch 2)]
          │ (TCP Port 9528)
          ▼
[Speedometer Cluster OMOWAY (960x360)]
```

Renderer menggambar antarmuka speedometer digital langsung ke `HardwareCanvas` pada resolusi native **960 x 360 piksel** @ 30 FPS tanpa overhead memori (*zero allocations during draw loop*).

---

## 3. Komponen Antarmuka Cockpit 960x360

Antarmuka terbagi menjadi 3 zona informasi modular:

### A. Panel Kiri (Navigasi & Panduan Arah) — `20..310 px`
* **Maneuver Arrow**: Ikon vektor panah petunjuk arah (Lurus, Belok Kiri/Kanan, Putar Balik, Bundaran).
* **Jarak Belokan**: Jarak real-time menuju titik manuver berikutnya (misal: `500 m`).
* **Nama Jalan**: Nama jalan tujuan (misal: `Jl. Jenderal Sudirman`).
* **Trip Card**: Perkiraan waktu tiba (`ETA 14:30`) dan sisa jarak tempuh (`4.2 km`).

### B. Panel Tengah (Digital Cockpit & Speedometer) — `330..630 px`
* **Busur Kecepatan Dinamis**: Busur tachometer 270° yang menyala dinamis:
  * 0 - 50 km/h: Neon Cyan
  * 50 - 80 km/h: Amber Orange
  * 80+ km/h: Neon Red
* **Digital Speedometer**: Angka kecepatan besar di tengah layar.
* **Sumber Kecepatan**:
  1. Live GPS Speedometer dari chip GPS HP (km/h riil saat motor melaju).
  2. Live MCU Speed dari telemetri motor.
* **Mode Transmisi**: Tombol kapsul mode berkendara (`[ P ]  [ ECO ]  [ D ]  [ S ]`).

### C. Panel Kanan (Telemetri & Status Cluster) — `650..940 px`
* **Jam & Kalender Digital**: Sinkron dengan waktu sistem smartphone.
* **Baterai Motor**: Pengukur kapasitas baterai horizontal dengan warna adaptif (Hijau > 40%, Oranye > 20%, Merah < 20%).
* **Sisa Jarak (Range)**: Estimasi jarak tempuh baterai dalam km.
* **Indikator Link**: Status koneksi port 9528 (`DESAY SV 9528 OK`).
* **Tema Otomatis**: Mendeteksi sinyal `Msg 37` dari sensor cahaya speedometer untuk beralih antara **OLED Night Mode** dan **High-Contrast Day Mode**.
