# Spesifikasi Protokol Kontrol Desay SV (Port 9527)

Dokumen ini menjelaskan struktur data biner dan JSON yang dipertukarkan melalui soket TCP port **9527** antara smartphone (client) dan speedometer motor listrik OMOWAY (Desay SV cluster server).

---

## 1. Format Frame Paket Biner

Setiap pesan yang dikirim dan diterima melalui port 9527 diawali dengan **8-byte Little-Endian Header**, diikuti oleh payload:

```text
+-----------------------+-----------------------+-----------------------+-----------------------+
| Byte 0 - 3 (uint32)   | Byte 4 - 7 (uint32)   | Byte 8 - 9 (uint16)   | Byte 10 ... N         |
| Subsystem Channel ID  | Payload Length (L)    | Message ID (CMD)      | Payload Data (L - 2)  |
+-----------------------+-----------------------+-----------------------+-----------------------+
```

### Rincian Header:
1. **`channel_id` (4 bytes, uint32 LE)**:
   * `0x00000001` (Channel 1 / CMD): **System & Navigation Channel** (Heartbeat, Handshake Kunci ECDH, Status Layar, Routing).
   * `0x00000002` (Channel 2 / VIDEO): **H.264 Video Stream Channel** (Enkapsulasi frame NALU H.264 pada TCP Port 9528).
   * `0x00000007` (Channel 7 / API): **Vehicle Telemetry Channel** (Mode Tampilan Day/Night, Speedometer, Device Info Resolusi Layar).
2. **`payload_length` (4 bytes, uint32 LE)**:
   * Panjang total payload dalam byte, dihitung dari `msg_id` (2 byte) ditambah panjang `payload_data`.
   * `total_packet_size = 8 + payload_length`.
3. **`msg_id` (2 bytes, uint16 LE)**:
   * Kode identifikasi perintah atau event.
4. **`payload_data` (`payload_length - 2` bytes)**:
   * Berupa data biner khusus (seperti ASN.1 Public Key, Uptime timestamp) atau string JSON UTF-8.

---

## 2. Saluran 1 (Channel 1 / CMD): System & Navigation

### A. Heartbeat Ping & Pong (`0x0009`)
Motor bertindak sebagai master yang mengirimkan Heartbeat Ping secara otomatis setiap **1000 ms (1 detik)**.

* **Motor -> Phone (Ping `0x0009`)**:
  * `channel_id`: `1` (CMD)
  * `payload_length`: `14` (`0x0000000E`)
  * `msg_id`: `9` (`0x0009`)
  * `payload`: 12 byte (4 byte sequence index uint32 LE + 8 byte timestamp motor uptime uint64 LE).
* **Phone -> Motor (Pong `0x0009`)**:
  * Smartphone **wajib** membalas dengan `msg_id = 9` (CMD channel 1) membawa kembali persis 12 byte payload (index + timestamp) tersebut.
  * Jika smartphone tidak membalas Pong dalam beberapa siklus, speedometer menganggap koneksi mati dan memutus soket TCP.
  * **PENTING**: Smartphone **TIDAK PERLU** mengirim `0x0009` mandiri ke motor. Motor adalah master penentu detak heartbeat.

### B. Security Handshake Key Exchange (`0x0031` / Msg 49) — GERBANG TAMPILAN
Saat koneksi terhubung, motor menginisialisasi negosiasi sesi keamanan kriptografis sebelum mengizinkan stream video dirender pada layar HUD cluster:

1. **Motor -> Phone (`0x0031` / 49)**:
   * `channel_id`: `1` (CMD)
   * `payload_length`: `93` (`0x0000005D`)
   * `msg_id`: `49` (`0x0031`)
   * `payload`: 91 byte ASN.1 DER SubjectPublicKeyInfo kurva eliptik **NIST P-256 (secp256r1 / prime256v1)**:
     ```text
     30 59 30 13 06 07 2a 86 48 ce 3d 02 01 06 08 2a 86 48 ce 3d 03 01 07 03 42 00 04 [64-byte X,Y point]
     ```

   > [!NOTE]
   > **Keamanan & Status Privasi Kunci Publik**:
   > - Deretan 27-byte awalan (`30 59 30 13 06 07 2a 86 48 ce 3d 02 01 06 08 2a 86 48 ce 3d 03 01 07 03 42 00 04`) adalah **ASN.1 DER header standar internasional (RFC 5480)** yang mendefinisikan algoritma EC Public Key kurva terbuka NIST P-256 (`prime256v1`). Header ini identik di semua implementasi TLS/ECDH standar dunia.
   > - Koordinat `[64-byte X,Y point]` adalah **Ephemeral Public Key** yang digenerate acak oleh cluster/HP secara dinamis per sesi, dan langsung dibuang setelah koneksi berakhir. Ini **bukan private key** dan **bukan kredensial rahasia**, sehingga sepenuhnya aman dipublikasikan secara tersanitasi.
2. **Phone -> Motor (Balasan Public Key Phone `0x0031` / 49)**:
   * Smartphone **wajib** men-generate pasangan kunci EC lokal (`secp256r1`), lalu menghitung Shared Secret ECDH (`KeyAgreement.getInstance("ECDH")`).
   * Smartphone mengirim kembali public key miliknya ke motor:
     * `channel_id`: `1`
     * `payload_length`: `93` (`total_packet_size = 101 bytes`)
     * `msg_id`: `49` (`0x0031`)
     * `payload`: 91 byte ASN.1 SubjectPublicKeyInfo lokal smartphone.
3. **Hasil Handshake**:
   * Motor memverifikasi kunci, memanggil `updateEcdhKeys`, dan memicu sinyal `requestKeyFrame=true`.
   * **LAYAR HUD TERBUKA**: Speedometer segera mengalihkan frame display dan mulai merender stream video H.264 dari port 9528!

### C. Deklarasi Resolusi & Status Layar (Channel 7, Msg 41)
Sesaat setelah soket TCP 9527 terhubung, smartphone mengirimkan resolusi target video:

* **Phone -> Motor (Device Info `Msg 41`)**:
  * `channel_id`: `7` (API)
  * `payload_length`: `20` (`total_packet_size = 28 bytes`)
  * `msg_id`: `41`
  * `payload`: String JSON:
    ```json
    {"size":"960x360"}
    ```

### D. Permintaan Tampilan Speedometer (`DS_MSG_HU_REQ_SHOW`)
Ketika rider menekan tombol menu **Maps / Navigasi** pada stang motor atau cluster:

* **Motor -> Phone**:
  * Mengirim payload teks JSON:
    ```json
    {"msg_id":"DS_MSG_HU_REQ_SHOW"}
    ```
* **Phone -> Motor (Konfirmasi Siap Stream)**:
  * Smartphone merespons dengan:
    * `channel_id`: `1`
    * `msg_id`: `0x0002`
    * Payload JSON:
      ```json
      {"msg_id":"DS_RESP_SHOW","result":0,"status":"STREAMING"}
      ```
  * Setelah respon ini dikirim, layar speedometer mulai merender frame video yang masuk di port 9528.

### E. Penutupan Tampilan Speedometer (`DS_MSG_HU_REQ_HIDE`)
Ketika rider keluar dari menu navigasi pada speedometer:

* **Motor -> Phone**:
  * Payload JSON:
    ```json
    {"msg_id":"DS_MSG_HU_REQ_HIDE"}
    ```
* Smartphone dapat menjeda encoder video untuk menghemat daya baterai.

### F. Informasi Panduan Rute (`DS_MSG_HU_REQ_ROUTE_INFO`)
Speedometer meminta info jarak & waktu sisa:

* **Motor -> Phone**:
  ```json
  {"msg_id":"DS_MSG_HU_REQ_ROUTE_INFO"}
  ```
* **Phone -> Motor**:
  * `channel_id`: `1`, `msg_id`: `0x0003`
  ```json
  {"msg_id":"DS_RESP_ROUTE_INFO","remain_dist":1200,"remain_time":180}
  ```

---

## 3. Saluran 7 (Channel 7 / API): Video Projection Signals & Telemetry

### A. Sinyal Tampilan Proyeksi Layar (MapProjectionSignal SHOW & HIDE)
Speedometer Desay SV mewajibkan sinyal eksplisit dari aplikasi untuk mengaktifkan framebuffer video setelah handshake ECDH:

1. **MapProjectionSignal SHOW (`Msg 1` / `0x0001`)**:
   * Dikirim oleh smartphone **segera setelah handshake ECDH (Msg 49) sukses**:
   * `channel_id`: `7`
   * `payload_length`: `12` (`0x0000000C`)
   * `msg_id`: `1` (`0x0001`)
   * `payload` (10 bytes):
     ```json
     {"code":0}
     ```
   * Total panjang frame di kawat jaringan: **20 bytes** (8 byte header + 2 byte msgId + 10 byte JSON).
   * **Efek**: Speedometer langsung mengalihkan layar cluster ke canvas video H.264 (Port 9528).

2. **MapProjectionSignal HIDE (`Msg 2` / `0x0002`)**:
   * Dikirim saat proyeksi dihentikan secara teratur:
   * `channel_id`: `7`
   * `msg_id`: `2` (`0x0002`)
   * `payload` (10 bytes):
     ```json
     {"code":0}
     ```

---

### B. Mode Tampilan Day / Night (`Msg 37` & `Msg 39`)
Motor secara berkala mengirimkan preferensi tampilan cluster (apakah siang atau malam hari):

* **Motor -> Phone (Permintaan Mode)**:
  * `channel_id`: `7`
  * `msg_id`: `37` (`0x0025`)
  * `payload`: JSON string:
    ```json
    {"mode":"night"}
    ```
    *(atau `{"mode":"day"}`)*

* **Phone -> Motor (Balasan Konfirmasi / ACK)**:
  * Smartphone **wajib** membalas konfirmasi penerimaan mode menggunakan **`msg_id = 39`** membawa body mode yang sama:
    * `channel_id`: `7`
    * `msg_id`: `39` (`0x0027`)
    * `payload`:
      ```json
      {"mode":"night"}
      ```
  * **Catatan Kritis**: Jika motor tidak menerima balasan `Msg 39`, motor akan mengulang `Msg 37` tiap 5 detik dan menganggap navigasi timeout, lalu keluar dari menu navigasi ke menu utama.

---

### C. Query Status Layar Speedometer (`Msg 27` & `Msg 10`)
* **Msg 27 (`0x001B`)**: Speedometer meminta query status kesiapan render. Balas dengan `channel_id = 7, msg_id = 27, {"code":0}`.
* **Msg 10 (`0x000A`)**: Sinkronisasi subsystem cluster pada Channel 7. Balas dengan `channel_id = 7, msg_id = 10, {"code":0}`.

