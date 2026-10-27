# OMOWAY CAN Bus Protocol Specification

> **Reverse-Engineering & Telemetry Decoding for OMOWAY Smart Electric Motorcycle CAN Bus**  
> Diuji & Diverifikasi menggunakan **MKS CANable v2 Pro** (Firmware SLCAN) pada port `COM3`.

Dokumen ini mendokumentasikan layer fisik, arsitektur bus, matriks CAN ID, struktur frame keamanan (E2E Rolling Counter & CRC), serta spesifikasi awal telemetri subsistem (BMS, VCU, MCU Powertrain, dan Cluster) pada motor listrik OMOWAY.

---

## 📌 Spesifikasi Layer Fisik & Link Layer

| Parameter | Nilai / Spesifikasi | Catatan |
| :--- | :--- | :--- |
| **Baud Rate** | **500.000 bps (500 kbps)** | Konfigurasi SLCAN: command `S6` |
| **Format ID** | **Standard 11-bit Identifier** (CAN 2.0A) | Seluruh frame menggunakan ID standar (bukan extended 29-bit) |
| **Data Length (DLC)** | **8 Byte** (sebagian besar frame) | DLC tetap 8 byte pada seluruh pesan periodik |
| **Bus Load / Throughput** | **~850 - 870 frames / detik** | Total ~40 unique CAN ID aktif secara simultan |
| **Resistor Terminasi** | **Wajib OFF / Open pada Sniffer** | Bus OMOWAY sudah memiliki terminasi internal (~60Ω) |
| **Pinout Hardware Sniffer** | `CAN_H`, `CAN_L`, `GND` | Wajib hubungkan GND ke ground motor untuk referensi potensial |

---

## 🛡️ Pola Keamanan E2E (Rolling Counter & CRC Checksum)

Banyak frame penting dengan frekuensi tinggi (50 Hz & 10 Hz) menerapkan mekanisme proteksi integritas data berbasis otomotif (mirip pola AUTOSAR E2E Profile):
* **Byte 6 (High Nibble)**: **Alive / Rolling Counter** bernilai `0` s/d `F` (0–15 siklus increment terus menerus).
* **Byte 7**: **CRC-8 / Checksum** yang berubah secara dinamis menyesuaikan data payload dan counter.

Frame yang menerapkan pola ini antara lain: `0x104`, `0x112`, `0x122`, `0x132`, `0x202`, `0x206`, `0x213`, `0x214`, `0x216`, `0x234`, `0x244`, `0x262`, `0x304`, dan `0x306`.

---

## 🔋 Spesifikasi Subsistem BMS (Battery Management System)

Salah satu temuan paling signifikan adalah pesan periodik **1 Hz (1000 ms)** dari BMS baterai utama:

### 1. Arsitektur Baterai
* Baterai bertipe **LFP (Lithium Iron Phosphate)** dengan konfigurasi **24S (24 Sel Seri)**.
* Nilai nominal pack: ~72V – 76.8V.
* Nilai terbaca saat diam (resting voltage): **3.288 V / sel** (`0x0CD8` = 3288 mV). Total tegangan pack: $24 \times 3.288\text{ V} = \mathbf{78.91\text{ V}}$.

### 2. Matriks Frame Tegangan Sel Baterai (Cell Voltages)

Setiap frame membawa data 4 sel baterai dalam format **16-bit Big-Endian (mV)**:

| CAN ID | Periode | Byte 0-1 | Byte 2-3 | Byte 4-5 | Byte 6-7 | Data Hex Terbaca | Keterangan |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`0x504`** | 1.0 s | Cell 1 | Cell 2 | Cell 3 | Cell 4 | `0C D8 0C D8 0C D8 0C D8` | Sel 1–4 = 3288 mV |
| **`0x514`** | 1.0 s | Cell 5 | Cell 6 | Cell 7 | Cell 8 | `0C D8 0C D8 0C D8 0C D8` | Sel 5–8 = 3288 mV |
| **`0x524`** | 1.0 s | Cell 9 | Cell 10 | Cell 11 | Cell 12 | `0C D8 0C D8 0C D8 0C D8` | Sel 9–12 = 3288 mV |
| **`0x534`** | 1.0 s | Cell 13 | Cell 14 | Cell 15 | Cell 16 | `0C D8 0C D8 0C D8 0C D8` | Sel 13–16 = 3288 mV |
| **`0x544`** | 1.0 s | Cell 17 | Cell 18 | Cell 19 | Cell 20 | `0C D8 0C D8 0C D8 0C D8` | Sel 17–20 = 3288 mV |
| **`0x554`** | 1.0 s | Cell 21 | Cell 22 | Cell 23 | Cell 24 | `0C D8 0C D8 0C D8 0C D8` | Sel 21–24 = 3288 mV |

### 3. Sensor Suhu Baterai (Temperature Probes)
* **`0x503`** (1.0 s): `47 47 47 47 08 03 FC 01`  
  * Byte 0 s/d 3 memuat 4 titik probe sensor suhu baterai: `0x47` (71 desimal).  
  * Dengan formula standar otomotif: $\text{Suhu (°C)} = \text{Raw} - 40$, maka suhu terbaca: **$71 - 40 = 31^\circ\text{C}$**.
* **`0x5F4`** (1.0 s): `46 47 46 00 00 00 00 46`  
  * Suhu tambahan / modul BMS: `0x46` ($70 - 40 = \mathbf{30^\circ\text{C}}$) dan `0x47` ($\mathbf{31^\circ\text{C}}$).

### 4. Status Pack & Arus (Current)
* **`0x564`** (1.0 s): `00 52 C0 04 F5 00 00 00`  
  * Memuat total status arus pack (amperemeter), status relay/kontaktor BMS, dan flags proteksi.

---

## 📍 Spesifikasi Metrik Cluster (Odometer, Sisa Jarak, & Trip)

Berdasarkan ground truth pembacaan speedometer langsung di motor OMOWAY:

### 1. Odometer Total: CAN ID `0x272` (Bytes 5–6)
* **Format**: 16-bit Big-Endian Unsigned Integer (`uint16_be`).
* **Resolusi / Skala**: **0.1 km (100 meter)** per bit ($1\text{ LSB} = 0.1\text{ km}$).
* **Formula**: $\text{Odometer (km)} = \text{Raw Value} \times 0.1$
* **Bukti Validasi**:
  * Nilai rekaman awal: `0x52B2` = $21170 \times 0.1 = \mathbf{2117.0\text{ km}}$.
  * Nilai rekaman live saat ini: `0x52B3` = $21171 \times 0.1 = \mathbf{2117.1\text{ km}}$ (+100 meter trip).

### 2. Sisa Jarak (Remaining Range): CAN ID `0x272` (Byte 7)
* **Format**: 8-bit Unsigned Integer (`uint8`).
* **Resolusi / Skala**: **1 km** per bit ($1\text{ LSB} = 1\text{ km}$).
* **Formula**: $\text{Sisa Jarak (km)} = \text{Raw Value}$
* **Bukti Validasi**:
  * Nilai rekaman live saat ini: `0x79` hex = **121 desimal ($\mathbf{121\text{ km}}$)** (persis sesuai layar cluster).
  * Nilai rekaman awal: `0x7C` hex = 124 km.

### 3. Trip Meter Saat Ini: CAN ID `0x303` (Byte 6)
* **Format**: 8-bit Unsigned Integer (`uint8`).
* **Resolusi**: **1 meter** (atau 10 meter).
* **Bukti Validasi**:
  * Nilai rekaman live saat ini: `0x64` hex = **100 desimal ($\mathbf{100\text{ meter}}$)**.

---

## 📋 Matriks Lengkap CAN ID (Snapshot Hasil Sniffing)

Berikut tabel seluruh 40 CAN ID yang teridentifikasi beserta frekuensi dan contoh muatan payload:

| CAN ID | DLC | Frekuensi | Interval | Sample Payload (Hex) | Estimasi Subsistem / Peran |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **`0x142`** | 8 | **99.4 Hz** | ~10 ms | `03 20 80 03 00 00 00 00` | **Fast Powertrain Loop** (kecepatan / throttle / status MCU) |
| **`0x104`** | 8 | 49.8 Hz | ~20 ms | `18 A8 27 16 05 07 60 81` | Motor Inverter Dynamics (Counter + CRC) |
| **`0x112`** | 8 | 49.8 Hz | ~20 ms | `00 03 00 00 00 00 A0 61` | Switch Status / Transmisi / Cluster status |
| **`0x114`** | 8 | 10.0 Hz | ~100 ms | `9B 24 E4 30 00 04 E0 32` | VCU Telemetry (Counter + CRC) |
| **`0x122`** | 8 | 49.8 Hz | ~20 ms | `21 00 04 50 00 00 0A EE` | Controller High Speed (Counter + CRC) |
| **`0x132`** | 8 | 49.8 Hz | ~20 ms | `4C E6 00 00 00 00 0A EC` | Powertrain Loop (Counter + CRC) |
| **`0x143`** | 8 | 49.8 Hz | ~20 ms | `00 0B 03 7C 4A 4E 8D 0B` | Dynamic Rolling Sensor / High-Res Timer |
| **`0x202`** | 8 | 49.8 Hz | ~20 ms | `7D 03 12 C1 2C 00 0A C0` | VCU Drive Mode & Speed Control |
| **`0x203`** | 8 | 49.8 Hz | ~20 ms | `12 CC 12 C0 17 67 D0 88` | Powertrain Feedback Limits |
| **`0x206`** | 8 | 48.2 Hz | ~20 ms | `00 00 32 10 00 7F F9 D6` | Inverter Target Torque / Current |
| **`0x213`** | 8 | 49.8 Hz | ~20 ms | `60 27 10 7F FF 08 0A A7` | Motor RPM / Rotor Position |
| **`0x214`** | 8 | 5.0 Hz | ~200 ms | `C8 36 C0 00 00 0B 07 73` | Thermal Status MCU/Motor |
| **`0x216`** | 8 | 48.2 Hz | ~20 ms | `00 00 00 00 C0 00 08 42` | Status Rem / Regenerative Braking |
| **`0x223`** | 8 | 19.7 Hz | ~50 ms | `00 5F 42 7D 01 F3 B2 9B` | Odometer / Trip status |
| **`0x224`** | 8 | 1.0 Hz | ~1000 ms| `01 66 C0 01 66 C0 00 06` | Static Vehicle Configuration |
| **`0x226`** | 8 | 48.2 Hz | ~20 ms | `00 00 00 F8 6A 51 BD 80` | High-Resolution Cluster Tick (Mirror dari 0x236) |
| **`0x233`** | 8 | 49.8 Hz | ~20 ms | `00 7F DF F7 FD FF 78 78` | Lighting / Body Control / Indicator Status |
| **`0x234`** | 8 | 10.0 Hz | ~100 ms | `1B 49 82 60 31 0B 83 1E` | Auxiliary Electrical Systems |
| **`0x236`** | 8 | 48.2 Hz | ~20 ms | `00 00 00 F8 6A 51 BD 80` | High-Resolution Cluster Tick (Mirror dari 0x226) |
| **`0x244`** | 8 | 5.0 Hz | ~200 ms | `00 00 00 00 00 00 70 53` | Diagnostic Heartbeat |
| **`0x262`** | 8 | 10.0 Hz | ~100 ms | `02 00 04 0A 00 00 06 F0` | Stand / Kickstand Sensor / P-Gear & Brake Multi-switch |
| **`0x272`** | 8 | 10.0 Hz | ~100 ms | `50 A1 92 D0 00 52 B3 79` | **Cluster Telemetry: Odometer (B5-B6) & Sisa Jarak (B7)** |
| **`0x282`** | 8 | 10.0 Hz | ~100 ms | `00 80 31 44 1B 14 13 2C` | State of Charge (SOC) / Battery Level to Cluster |
| **`0x302`** | 8 | 10.0 Hz | ~100 ms | `00 00 04 00 70 80 00 00` | Cruise Control / Riding Modes |
| **`0x303`** | 8 | 2.0 Hz | ~500 ms | `84 E3 F5 00 00 00 64 7C` | **Trip Meter Data (Byte 6 = meter)** |
| **`0x304`** | 8 | 5.0 Hz | ~200 ms | `00 00 00 00 00 78 07 28` | Ambient Light / Headlamp Mode |
| **`0x306`** | 8 | 9.6 Hz | ~100 ms | `10 00 00 00 00 00 0F 08` | Cluster Screen Event Trigger |
| **`0x323`** | 8 | 10.0 Hz | ~100 ms | `00 22 7B FF 47 44 7F FF` | Tire Pressure / ABS / Wheel Speed Sensor |
| **`0x502`** | 8 | 1.0 Hz | ~1000 ms| `00 00 00 00 00 00 00 00` | BMS Global Error Flags (0 = Normal) |
| **`0x503`** | 8 | 1.0 Hz | ~1000 ms| `47 47 47 47 08 03 FC 01` | **BMS Battery Probes Temperature** |
| **`0x504`** | 8 | 1.0 Hz | ~1000 ms| `0C D8 0C D8 0C D8 0C D8` | **BMS Cell 1–4 Voltages** |
| **`0x512`** | 8 | 1.0 Hz | ~1000 ms| `00 4C 7E AA 1A 0F 2B 3B` | BMS Battery Serial / Rolling Security |
| **`0x514`** | 8 | 1.0 Hz | ~1000 ms| `0C D8 0C D8 0C D8 0C D8` | **BMS Cell 5–8 Voltages** |
| **`0x522`** | 8 | 1.0 Hz | ~1000 ms| `00 26 29 98 F1 C3 ED 4A` | BMS Battery Health (SOH) / Cycle Count |
| **`0x524`** | 8 | 1.0 Hz | ~1000 ms| `0C D8 0C D8 0C D8 0C D8` | **BMS Cell 9–12 Voltages** |
| **`0x534`** | 8 | 1.0 Hz | ~1000 ms| `0C D8 0C D8 0C D8 0C D8` | **BMS Cell 13–16 Voltages** |
| **`0x544`** | 8 | 1.0 Hz | ~1000 ms| `0C D8 0C D8 0C D8 0C D8` | **BMS Cell 17–20 Voltages** |
| **`0x554`** | 8 | 1.0 Hz | ~1000 ms| `0C D8 0C D8 0C D8 0C D8` | **BMS Cell 21–24 Voltages** |
| **`0x564`** | 8 | 1.0 Hz | ~1000 ms| `00 52 C0 04 F5 00 00 00` | **BMS Total Current & Pack Voltage** |
| **`0x5F4`** | 8 | 1.0 Hz | ~1000 ms| `46 47 46 00 00 00 00 46` | **BMS Extra Temperature & Status** |

---

## 🛑 Hasil Decoding Sinyal Rem (Brake Signal)

Dari hasil *Differential Analysis* antara kondisi rem bebas vs rem ditekan, sinyal pengereman terdeteksi pada 3 frame utama dengan korelasi 100%:

### 1. Saklar Switch & Mode Kendaraan: CAN ID `0x262` (Frekuensi: 10 Hz)
* **Byte 4 (Master Safety & State Bitfield)**:
  * **Bit 5 (`0x20`)**: **Tuas Rem Ditekan (Brake Switch Active)**
  * **Bit 6 (`0x40`)**: **Mode Parkir / Standby (P-Gear / Proximity Welcome State)**
  * **Bit 7 (`0x80`)**: **Lampu Sein Aktif (Turn Signal Active)**
  * *Kombinasi Nilai*:
    * `0x00`: Siap Jalan (Drive Mode / Rem Bebas).
    * `0x20`: Rem Ditekan saat berkendara.
    * `0x40`: Parkir / Standar Samping / Standby Proximity.
    * `0x60` (`0x40 | 0x20`): Parkir / Standby + Tuas Rem Ditekan.
    * `0x80`: Lampu Sein menyala.

### 2. Status Rem Dinamis: CAN ID `0x226` & `0x236` (Frekuensi: ~50 Hz / 20 ms)
* **Byte 2**:
  * Nilai `0x00`: **Rem Bebas (OFF)**
  * Nilai `0x01` (Bit 0 = `1`): **Status Rem Aktif (Active / Interlock)**

### 3. Permintaan Torsi Regeneratif (Regen Braking): CAN ID `0x236` (Frekuensi: ~50 Hz)
* **Byte 0 s/d 1** (16-bit Signed Big-Endian Integer):
  * `0x00 0x00` ($0$): Kondisi diam tanpa rem.
  * `0xFF 0xFA` ($-6$ dalam two's complement): Permintaan torsi pengereman regeneratif elektrik (regenerative torque request) ke controller motor saat tuas rem ditarik.
---

## 💡 Spesifikasi Kontrol Lampu DRL Putih (Daytime Running Light Lifecycle)

Berdasarkan pengujian rekaman transisi siklus penuh ([drl_breathing_wake.csv](../examples/drl_breathing_wake.csv), 14.164 frame):

### 1. Fase 1: DRL MATI (Kontak OFF / Power Sleep)
* **CAN ID `0x233`**: **`00 00 00 00 00 00 00 00`**
  * Seluruh byte bitmask LED mati (`0x00`).
  * Byte 6 & 7 (PWM Duty Cycle): **`0 / 0`** (daya LED 0%).
* **CAN ID `0x112`**: Byte 1 bernilai **`0x00`** (`00 00 00 00 00 00 ...` = Status Kontak Mati).

### 2. Fase 2: DRL BERGERAK (Running Sweep / Chase Animation)
* **Pemicu**: Kontak ON atau transisi aktivasi.
* **CAN ID `0x233`**:
  * Byte 3, 4, dan 5 secara dinamis memutar sequence data LED berjalan (terekam 123 transisi frame pada interval ~20 ms):
    * `00 7F DF F7 F9 FF 78 78`
    * `00 7F DF F7 FD FE 78 78`
    * `00 7F DF F7 FA 00 78 78`
    * `00 7F DF F8 01 FE 78 78`
    * `00 7F DF F8 01 FF 78 78`
  * Byte 6 & 7 (PWM Duty Cycle): **`120 / 120`** (`0x78` = 47% daya kontinu).

### 3. Fase 3: DRL NYALA FULL (Solid Steady ON)
* **Kondisi**: Motor dihidupkan / siap jalan (*engine/inverter active*).
* **CAN ID `0x233`**: **`19 7F DF F7 FD FF 78 78`**
  * **Byte 0**: Nilai berubah menjadi **`0x19`** (flag operasional motor menyala kontinu).
  * Seluruh 32 diode LED (16 Sayap Kiri `L01..L16` + 16 Sayap Kanan `R01..R16`) menyala solid penuh secara simetris tanpa ada diode mati (termasuk L08 dan L14).
  * Byte 6 & 7 (PWM Duty Cycle): **`120 / 120`** (`0x78` = 47.1% kontinu).
* **CAN ID `0x112`**: Byte 1 bernilai **`0x03`** (`00 03 00 00 00 00 ...` = Status Kontak ON).

### 4. Fase 4: DRL BERNAFAS (Breathing Fade saat Proximity BLE)
* **Kondisi**: Motor mati / standby, rider mendekat dengan BLE key / HP.
* **CAN ID `0x233`**: **`00 7F DF ... 78 78`**
  * **Byte 0**: Nilai bernilai **`0x00`** (standby / greet mode).
  * Mengatur modulasi intensitas cahaya secara bertahap naik-turun halus (efek nafas) dengan siklus ~1.2 s.

### 5. Pemetaan Alamat Bit LED Addressable (32 Segmen Fisik + PWM)
Headlight DRL OMOWAY dikendalikan secara individual per channel segmen diode LED melalui 5 register bitfield (Bytes 1..5) dan 2 register PWM brightness (Bytes 6..7):

| Blok Komponen | Register CAN | Jumlah Bit | Pemetaan Alamat Segmen | Keterangan Fisik |
| :--- | :---: | :---: | :--- | :--- |
| **Sayap Kiri (L01..L16)** | Byte 1 & 2 (`B1..B2`)| 16 LED | Diode `L01` s/d `L16` | Seluruh 16 segmen sayap kiri (termasuk L08 & L14) menyala solid |
| **Sayap Kanan (R01..R16)**| Symmetrical (`B1..B4`)| 16 LED | Diode `R01` s/d `R16` | Seluruh 16 segmen sayap kanan menyala solid simetris |
| **Emblem / Projector Dot**| Byte 5 (`B5`) | 8 bit (`b0..b7`) | Center Optic Accent | Aksen projector tengah / logo OMO |
| **Kecerahan Kiri (PWM)**  | Byte 6 (`B6`) | `uint8` (0..255)| `120` = 47.1% Duty Cycle | Modulasi intensitas cahaya sisi kiri |
| **Kecerahan Kanan (PWM)** | Byte 7 (`B7`) | `uint8` (0..255)| `120` = 47.1% Duty Cycle | Modulasi intensitas cahaya sisi kanan |

---

## 🏎️ Spesifikasi Powertrain Dynamics: Kecepatan, Cruise Control, RPM, & Suhu

Berdasarkan pengujian langsung di atas standar 2 (center stand) dengan Cruise Control aktif pada kecepatan 15 km/h:

### 1. Kecepatan Kendaraan & Cruise Control: CAN ID `0x122` & `0x233` (Frekuensi: ~50 Hz)
* **`0x122:B4` & `0x233:B0` (`uint8`)**: **Kecepatan Real-time Roda Belakang (km/h)**
  * Resolusi: **$1\text{ km/h}$** per bit ($1\text{ LSB} = 1\text{ km/h}$).
  * Validasi pengujian riil (Standar 2):
    * **0 km/h (Diam)**: `0x00`
    * **Cruise 10 km/h**: `0x0A` (10 desimal)
    * **Cruise 11 km/h**: `0x0B` (11 desimal)
    * **Cruise 15 km/h**: `0x0F` (15 desimal)
* **`0x122:B2` (Flag Status Kontrol)**:
  * **Bit 4 (`0x10`)**: **Cruise Control Active**
  * Nilai diam / rem ditekan: `0x04`
  * Nilai saat Cruise Aktif: `0x14` (`0x04 | 0x10`)

### 2. Putaran Mesin (Motor BLDC RPM): CAN ID `0x213` (Frekuensi: 49.8 Hz)
* **Bytes 3–4 (`uint16_be`, Big-Endian dengan Offset `0x8000` / `32768`)**: **Rotasi Poros Motor BLDC (RPM)**
  * Formula:
    $$\text{RPM} = \max\left(0, ((\text{Byte 3} \ll 8) \mid \text{Byte 4}) - 0x8000\right)$$
  * Saat motor diam / roda berhenti, payload mengirim `0x7FFF` ($32767$), sehingga $32767 - 32768 = -1 \to \mathbf{0\text{ RPM}}$.
  * Validasi pengujian fisik riil:
    * **0 km/h (Diam)**: `0x7F 0xFF` $\to \mathbf{0\text{ RPM}}$
    * **10 km/h**: `0x82 0xE4` $\to 33508 - 32768 = \mathbf{740\text{ RPM}}$ (sesuai speedometer 730–740 RPM)
    * **11 km/h**: `0x83 0x2B` $\to 33579 - 32768 = \mathbf{811\text{ RPM}}$ (sesuai speedometer 800–817 RPM)
    * **15 km/h**: `0x84 0x52` $\to 33874 - 32768 = \mathbf{1106\text{ RPM}}$ (sesuai kisaran ~1100 RPM di speedometer)
  * Rasio konstan powertrain: $\approx 73.5\text{ RPM}$ per $1\text{ km/h}$.

### 3. Sensor Suhu Powertrain (BLDC Motor & Inverter MCU): CAN ID `0x323` (Frekuensi: ~10 Hz)
* **Byte 4 (`uint8`)**: **Suhu Inverter / MCU Controller (°C)**
  * Formula Otomotif: $\text{Suhu (°C)} = \text{Raw} - 40$
  * Nilai terbaca: **`0x47`** ($71\text{ desimal}$) $\to 71 - 40 = \mathbf{31^\circ\text{C}}$ (dan $72 - 40 = 32^\circ\text{C}$ saat berjalan).
* **Byte 5 (`uint8`)**: **Suhu Motor Listrik BLDC (°C)**
  * Formula Otomotif: $\text{Suhu (°C)} = \text{Raw} - 40$
  * Nilai terbaca: **`0x42`** ($66\text{ desimal}$) $\to 66 - 40 = \mathbf{26^\circ\text{C}}$ (sesuai tampilan cluster 26°C).

### 4. Arsitektur Trip Meter (Speedometer Cluster Volatile)
* Sebelumnya `0x303:B6` sempat disangka Trip Meter karena bernilai `0x64` ($100$), namun terbukti bahwa byte tersebut adalah **rolling uptime counter** VCU ($60, 61, 62 \dots$).
* Pada sistem kelistrikan motor OMOWAY, nilai **Trip Meter dikelola secara lokal dan volatil oleh Speedometer Head Unit** (bukan dikirim periodik oleh VCU).
* Nilai Trip secara otomatis ter-reset ke $0.0\text{ km}$ setiap kali kontak motor dimatikan dan dinyalakan kembali (*power cycle*).
* Di web dashboard, Trip dihitung secara presisi dari selisih Odometer (`0x272:B5-B6`) sejak kontak motor ON:
  $$\text{Trip (km)} = \text{ODO Saat Ini} - \text{ODO Saat Motor Dinyalakan}$$

---

## 🛠️ Tooling & Skrip Analisis

Seluruh utilitas pengujian tersedia di direktori `examples/`:

1. **[omoway_can_sniffer.py](../examples/omoway_can_sniffer.py)**  
   Merekam aliran CAN bus ke format `.csv` dan `.candump.log` dengan opsi hitung mundur (`--delay`):
   ```bash
   python examples/omoway_can_sniffer.py --port COM3 --delay 3 --duration 5 --csv examples/can_brake_pressed.csv --log examples/can_brake_pressed.candump.log
   ```

2. **[diff_analyzer.py](../examples/diff_analyzer.py)**  
   Membandingkan rekaman baseline dengan aksi fisik untuk menemukan byte/bit yang berubah:
   ```bash
   python examples/diff_analyzer.py --baseline examples/can_capture.csv --action examples/can_brake_pressed.csv --name "Brake Test"
   ```

3. **[analyze_dump.py](../examples/analyze_dump.py)**  
   Menganalisis variasi payload, menghitung jumlah payload unik, dan mengidentifikasi rolling byte counter.
