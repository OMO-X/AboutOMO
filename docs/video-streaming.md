# Spesifikasi Video Streaming H.264 (Port 9528)

Dokumen ini menjelaskan spesifikasi kompresi dan transmisi video untuk menampilkan grafis HUD / navigasi pada layar speedometer motor OMOWAY melalui soket TCP port **9528**.

---

## 1. Arsitektur Video Streaming & Protokol Framing Port 9528

Motor OMOWAY menggunakan arsitektur streaming berbasis soket TCP port **9528** dengan enkapsulasi **Desay SV 8-Byte Multiplexing Header**:
* **Bukan RTSP**: Tidak ada handshake RTSP (`DESCRIBE`, `SETUP`, `PLAY`) dan tidak menggunakan RTP/RTCP di port 554/8554.
* **Bukan Raw Annex-B Standalone**: Mengirim byte H.264 mentah (`00 00 00 01`) tanpa header Desay SV akan menyebabkan server cluster membaca byte pertama sebagai Channel ID `0x01000000` (`16.777.216`), menganggap koneksi korup, dan langsung menutup soket (`TCP FIN`) dalam tempo 16 ms (menghasilkan error `Broken pipe` / `EPIPE`).
* **Format Framing Wajib (Desay SV Channel 2)**: Setiap frame H.264 (baik IDR maupun P-Frame) **wajib** diawali dengan 8-byte Little-Endian Header:

```text
+-----------------------------------+-----------------------------------+-----------------------------+
| Byte 0 - 3 (uint32 LE)            | Byte 4 - 7 (uint32 LE)            | Byte 8 ... N                |
| Channel ID = 2 (Video Subsystem)  | Payload Length (N - 8 bytes)      | H.264 NALUs (Annex-B Frame) |
+-----------------------------------+-----------------------------------+-----------------------------+
```

```kotlin
// Contoh Implementasi Kotlin:
val header = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN)
header.putInt(2)            // Subsystem Channel ID = 2 (Video)
header.putInt(frame.size)   // Panjang paket H.264 NALU
socket.getOutputStream().write(header.array())
socket.getOutputStream().write(frame)
```

---

## 2. Parameter Encoder Video

Agar layar speedometer dapat mendecode dan menampilkan gambar tanpa glitch atau buffer drop, encoder pada smartphone harus dikonfigurasi dengan parameter eksak berikut:

| Parameter | Nilai | Catatan Implementasi |
| :--- | :--- | :--- |
| **MIME Type** | `video/avc` (H.264) | Hardware codec (Qualcomm / Exynos / MediaTek) |
| **Lebar (Width)** | **960 piksel** | Resolusi native horizontal HUD |
| **Tinggi (Height)** | **360 piksel** | Resolusi native vertikal HUD (Rasio ~2.67:1) |
| **DPI Virtual** | **160 dpi** | Kepadatan piksel layar cluster |
| **Framerate** | **30 FPS** | Kecepatan refresh ideal |
| **Bitrate Target** | **2.000.000 bps (2 Mbps)** | Sesuai konfigurasi internal `libdatajar.so` |
| **Bitrate Mode** | **CBR (Constant Bitrate)** | `BITRATE_MODE_CBR` (Mode 2) untuk latensi rendah |
| **I-Frame Interval** | **1 detik** | Menjamin speedometer lekas mendapat keyframe baru |
| **H.264 Profile** | **Profile 8 (High Profile)** | Baseline Profile juga didukung secara kompatibel |

---

## 3. Rincian NALU & Parameter Set (SPS & PPS)

Decoder perangkat keras pada headunit Desay SV memerlukan Sequence Parameter Set (SPS) dan Picture Parameter Set (PPS) di awal koneksi:

1. **Parameter Sets Awal**:
   * **SPS (`csd-0`)**: 22 byte NALU tipe 7 (`0x67` atau `0x27`).
   * **PPS (`csd-1`)**: 9 byte NALU tipe 8 (`0x68` atau `0x28`).
2. **Keyframe (IDR Frame)**:
   * Setiap IDR-frame (tipe 5, `0x65`) disarankan selalu didahului oleh SPS dan PPS terbaru (`prepend-sps-pps-to-idr-frames=1`) agar speedometer dapat langsung menampilkan gambar saat baru dinyalakan tanpa menunggu siklus panjang.
3. **P-Frame**:
   * Frame delta dikirim setiap ~33 ms (30 fps).

---

## 4. Contoh Konfigurasi Android `MediaCodec` (Kotlin)

```kotlin
val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, 960, 360).apply {
    setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface)
    setInteger(MediaFormat.KEY_BIT_RATE, 2_000_000)
    setInteger(MediaFormat.KEY_FRAME_RATE, 30)
    setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1)
    setInteger(MediaFormat.KEY_BITRATE_MODE, MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CBR)
    setInteger("latency", 0)
    setInteger("priority", 0)
    setInteger("prepend-sps-pps-to-idr-frames", 1) // Wajib agar SPS/PPS menempel di setiap I-frame
}

val encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
encoder.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
val inputSurface = encoder.createInputSurface()
encoder.start()
```

### Proyeksi Layar Android (`MediaProjection` + `VirtualDisplay`)
Untuk screen mirroring ke layar cluster:
1. **Flag Mandatori**: Wajib menggunakan `DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR` (nilai `16`). Jika flag bernilai `0`, Android tidak akan merender konten layar utama ke surface encoder sehingga video stream tidak akan menghasilkan frame!
2. **Android 14 Callback**: Wajib memanggil `mediaProjection.registerCallback(callback, handler)` sebelum `createVirtualDisplay()`.
3. **Sinkronisasi Keyframe (Msg 11)**: Saat speedometer mengirim `Channel 7, Msg 11`, panggil:
   ```kotlin
   mediaCodec.setParameters(Bundle().apply {
       putInt(MediaCodec.PARAMETER_KEY_REQUEST_SYNC_FRAME, 0)
   })
   ```
   untuk segera mengirimkan I-Frame (IDR) baru.

---

## 5. Urutan Inisialisasi Kritis & Pencegahan "Broken Pipe"

Berdasarkan arsitektur penerima video Desay SV, terdapat ketergantungan sekuensial mutlak antara saluran kontrol (Port 9527) dan saluran video (Port 9528):

1. **Gating Koneksi Port 9528**:
   * Soket video TCP port 9528 **TIDAK BOLEH** mengirim data sebelum saluran kontrol (Port 9527) menyelesaikan Handshake Keamanan ECDH (`Msg 49`) dan mengirim `MapProjectionSignal SHOW` (`Channel 7, Msg 1`).
   * Jika frame video dikirim sebelum handshake selesai, modul decoder Desay SV akan menolak paket dan memutuskan soket (`TCP RST`), yang menyebabkan kesalahan `EPIPE (Broken pipe)` pada smartphone.
2. **Paketisasi SPS/PPS Bersama IDR**:
   * Header SPS (22 bytes) dan PPS (9 bytes) tidak boleh dikirim sebagai paket biner telanjang (standalone non-slice) ke soket video, karena parser decoder cluster dapat mengalami drop buffer.
   * SPS dan PPS harus dilekatkan langsung (*prepended*) di awal paket IDR KeyFrame pertama (`[00 00 00 01 SPS] [00 00 00 01 PPS] [00 00 00 01 IDR]`).
3. **Penanganan Pemulihan Soket (Auto-Reconnect)**:
   * Jika terjadi `Broken pipe` atau koneksi terputus saat streaming aktif, soket lama wajib segera ditutup (`disconnect()`), lalu dijadwalkan koneksi ulang bertahap (throttled reconnect ~1 detik), disusul permintaan I-Frame baru (`requestKeyFrame()`) agar speedometer lekas pulih.

