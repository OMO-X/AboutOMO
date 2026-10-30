# Arsitektur Native Android Auto Receiver & HUD Cockpit (960x360 @ 60 FPS)

Dokumen ini menjelaskan bagaimana aplikasi **UMOX** menjalankan **Native Android Auto Headunit Receiver (`127.0.0.1:5277`)** di dalam HP yang sama, melakukan transcoding hardware zero-copy melalui **OpenGL ES 2.0 (`EglSurfaceCropper`)** lengkap dengan **HUD Safe Margin (`840x270`)** dan **Shader Pencerah Siang Hari (Anti-Overlay Daylight Boost)**, lalu mengalirkannya ke speedometer OMOWAY pada **60 FPS tanpa delay**.

---

## 1. Perbandingan Metode Proyeksi ke Speedometer OMOWAY

| Fitur | Screen Mirroring (`MediaProjection`) | Native Android Auto Receiver (`127.0.0.1:5277`) |
| :--- | :--- | :--- |
| **Izin Sistem** | Wajib klik dialog izin rekam layar setiap sesi | **Tanpa izin rekam layar**, jalan otomatis di background |
| **Kondisi Layar HP** | Layar HP harus menyala dan menampilkan peta | **Layar HP bebas dimatikan (dikunci)** di saku/bagasi |
| **Rasio & Resolusi** | Sering gepeng / letterbox karena rasio HP `20:9` | **Widescreen Native** (`1120x360` -> `840x270` di dalam `960x360`) |
| **HUD Safe Margin** | Tertutup angka `0 km/h`, jam, dan bar baterai motor | **Otomatis menyisakan margin aman** untuk indikator HUD asli motor |
| **Kecerahan Siang Hari** | Redup tertutup *dark overlay* bawaan OMOWAY | **GPU Fragment Shader** mengangkat Gamma, Brightness, Contrast & Saturasi |

---

## 2. Pipeline End-to-End Zero-Copy (60 FPS)

```text
[Google Android Auto App (Head Unit Server: 127.0.0.1:5277)]
          │  (TLS 1.2 + AAP Protocol Channel 3 Video)
          │  (1280x720 @ 60 FPS dengan margin 160x360 -> 1120x360 Active UI)
          ▼
[MediaCodec Hardware H.264 Decoder]
          │  (Render langsung ke SurfaceTexture OES Zero-Copy)
          ▼
[EglSurfaceCropper (OpenGL ES 2.0 @ 960x360)]
  ├── Crop margin hitam Android Auto (uTexCropX / uTexCropY)
  ├── HUD Safe Margin Viewport: glViewport(0, 45, 840, 270)
  └── Fragment Shader: Anti-Overlay Daylight Color Boost (Gamma + Contrast + Brightness + Saturation)
          │  (Hardware-accelerated EGL eglSwapBuffers + eglPresentationTimeANDROID)
          ▼
[MediaCodec Hardware H.264 Encoder (960x360 @ 60 FPS, 4 Mbps, GOP 6 / 100ms)]
          │
          ▼
[Desay SV 18-Byte Video Framing (Ch 2 + Codec=1 + Type=1|2 + PtsUs + SPS/PPS)]
          │  (TCP Port 9528, SO_SNDBUF=16KB, 100ms Bounded Live Queue)
          ▼
[Speedometer Cluster OMOWAY (192.168.2.1:9528)]
```

---

## 3. Protokol Loopback Android Auto (`127.0.0.1:5277`)

### A. Deteksi Server Tanpa Mengganggu Sesi (`EADDRINUSE` Probe)
Komponen `GH.DHUService` (Head Unit Server milik aplikasi Android Auto di port `5277`) hanya menerima **satu koneksi TCP** lalu langsung menutup socket listener-nya.
* **JANGAN** mengecek status server dengan `Socket().connect(127.0.0.1, 5277)` lalu menutupnya! Koneksi kosong tanpa handshake TLS AAP akan membuat `GH.DHUService` menganggap sesi telah selesai dan **mematikan Head Unit Server**.
* **Cara Benar**: Coba lakukan `ServerSocket()` bind pada `127.0.0.1:5277`:
  * Jika lempar `BindException (EADDRINUSE)` -> Port `5277` sedang aktif didengarkan oleh Android Auto!
  * Jika berhasil bind -> Segera tutup `ServerSocket`, berarti Head Unit Server belum aktif.

### B. Handshake AAP & 5-Channel `ServiceDiscoveryResponse`
Setelah TCP terhubung ke `127.0.0.1:5277`:
1. **Version Exchange**: Kirim `Ch 0, Flags=3 (FIRST|LAST), Msg=0x0001 (VersionRequest: major=1, minor=7)`.
2. **TLS 1.2 Handshake (`SSLEngine` Client Mode)**:
   * Menggunakan sertifikat client headunit publik dan private key RSA-2048 yang di-dekripsi (`alg/transformation`, key `"headunit"`).
   * Enkapsulasi paket `TLS Handshake` di dalam pesan `Ch 0, Msg=0x0003 (SslHandshake)`.
   * Kirim `Ch 0, Msg=0x0004 (AuthComplete: status=0)`.
3. **`ServiceDiscoveryResponse` (`Ch 0, Msg=0x0006`)**:
   Mengiklankan 5 channel layanan agar Android Auto mengirim video widescreen penuh tanpa memblokir sesi:
   * **Channel 1 (Input Source)**: Touchscreen `1280x720` + daftar keycode tombol stang/media (`KEYCODE_DPAD_*`, `KEYCODE_ENTER`, `KEYCODE_BACK`, `KEYCODE_MEDIA_PLAY_PAUSE`, `KEYCODE_MEDIA_NEXT`, `KEYCODE_MEDIA_PREVIOUS`, `KEYCODE_VOLUME_UP/DOWN`).
   * **Channel 2 (Sensor Source)**: `SENSOR_DRIVING_STATUS_DATA` (Unrestricted = `0`), `SENSOR_NIGHT_MODE` (Default `is_night = false` agar terang di siang hari).
   * **Channel 3 (Media Sink - Video)**: `codec = MEDIA_CODEC_VIDEO_H264_BP (1)`, `resolution = 1280x720 (2)`, `frame_rate = 60 FPS (1)`, `width_margin = 160`, `height_margin = 360` (menghasilkan area aktif **`1120 x 360`**), `density = 140 DPI`.
   * **Channel 4 (Audio Sink - Guidance)**: `48 kHz, 16-bit, Mono`.
   * **Channel 5 (Audio Sink - System)**: `16 kHz, 16-bit, Mono`.

---

## 4. HUD Safe Margin (`840x270` di dalam `960x360`)

Speedometer OMOWAY menggambar lapisan indikator HUD bawaan motor **di atas** permukaan video `960x360`:
* **Sisi Kanan (`120 px`)**: Tertutup angka speedometer besar (`0 km/h`) dan indikator lampu/mode (`D` / `N`).
* **Sisi Atas (`45 px`)**: Tertutup jam (`08:44`) di kiri atas dan ikon status hijau di kanan atas.
* **Sisi Bawah (`45 px`)**: Tertutup bar baterai (`93% 197 km`), status `Tidak Terhubung`, dan `0.0 kW`.

Dengan mengatur viewport OpenGL di [`EglSurfaceCropper.kt`](file:///c:/Users/armadeas/UMOX/umox-app/app/src/main/java/com/umox/app/stream/EglSurfaceCropper.kt):
```kotlin
GLES20.glViewport(
    /* x = */ marginLeftPx,                                   // Default: 0 px
    /* y = */ marginBottomPx,                                 // Default: 45 px
    /* width = */ 960 - marginLeftPx - marginRightPx,         // Default: 840 px
    /* height = */ 360 - marginTopPx - marginBottomPx         // Default: 270 px
)
```
Seluruh elemen antarmuka Google Maps dan kontrol musik Android Auto tampil utuh tanpa terpotong angka kecepatan maupun status baterai motor, dan margin ini dapat diatur secara **real-time** melalui slider di aplikasi UMOX.

---

## 5. Rekayasa Shader GPU Anti-Overlay Siang Hari (Daylight Boost)

Headunit OMOWAY menerapkan lapisan gelap transparan (*dark translucent vignette/scrim*) di atas permukaan video agar angka HUD putih mudah terbaca. Akibatnya, pada siang hari yang terik, tampilan peta menjadi redup.

UMOX menyematkan **Fragment Shader OpenGL ES 2.0 real-time** yang memproses setiap piksel sebelum masuk ke encoder H.264:

```glsl
// 1. Gamma Lift (< 1.0 mengangkat bayangan & midtone gelap tanpa membuat putih pecah)
rgb = pow(clamp(rgb, 0.0, 1.0), vec3(uGamma));        // Preset Siang: 0.68

// 2. Contrast & Brightness Boost
rgb = (rgb - 0.5) * uContrast + 0.5 + uBrightness;    // Contrast: 1.32x, Brightness: +0.14

// 3. Saturation Boost (agar warna jalan biru & rambu hijau tetap hidup)
float luma = dot(rgb, vec3(0.2126, 0.7152, 0.0722));
rgb = mix(vec3(luma), rgb, uSaturation);              // Saturation: 1.35x
```

Seluruh parameter (`Gamma`, `Brightness`, `Contrast`, `Saturation`, serta preset `Standar Siang`, `Siang Terik (Max)`, dan `Normal (Malam)`) dapat diubah secara **live** dari layar aplikasi UMOX saat berkendara dan langsung terlihat di layar speedometer motor dalam `< 16 ms`!
