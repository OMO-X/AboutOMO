# Spesifikasi Jaringan & Wi-Fi Direct (P2P)

Dokumen ini menjelaskan topologi jaringan Wi-Fi Direct (P2P) antara smartphone dan speedometer motor OMOWAY, penugasan alamat IP, serta perilaku reinvocation grup persistent.

---

## 1. Topologi Jaringan Wi-Fi P2P

Speedometer motor OMOWAY berfungsi sebagai **Group Owner (GO)** mandiri yang memancarkan SSID Wi-Fi Direct:

* **SSID P2P Group Owner**: `DIRECT-OMO-xx-xx-xx` (diambil dari 3 byte terakhir MAC address, misal: `DIRECT-OMO-XX-XX-XX`).
* **MAC Address**: Disesuaikan dengan MAC P2P perangkat (format: `XX:XX:XX:XX:XX:XX`).
* **Frekuensi Operasi**: **5745 MHz** (Wi-Fi 5 GHz, Band 4 / Channel 149).
* **Keamanan / WPS**: WPS PBC (Push Button Configuration) dengan kredensial persistent WPA2-PSK.
* **Peran Smartphone**: **P2P Client** (Group Client, `groupOwnerIntent = 0`).

---

## 2. Alokasi Alamat IP (Subnet 192.168.2.0/24)

Headunit menjalankan DHCP server internal pada interface Wi-Fi Direct miliknya:

* **IP Headunit / Gateway**: **`192.168.2.1`** (Statis)
* **IP Smartphone (Client)**: **`192.168.2.145`** (Diberikan secara dinamis via DHCP)
* **Subnet Mask**: `255.255.255.0` (`/24`)
* **Interface Android**: `p2p-wlan0-0` (atau `p2p0`)

Port terbuka yang terverifikasi aktif pada IP `192.168.2.1` (Headunit Cluster):
* **Port 9527 (TCP)**: Desay SV Control & Telemetry Protocol Channel (ECDH handshake, heartbeat ping/pong, sinyal SHOW/HIDE, deklarasi resolusi 960x360, telemetri mode day/night).
* **Port 9528 (TCP)**: Desay SV Video Stream (Wajib dengan 8-byte Little-Endian Framing: `Channel ID = 2`, `Payload Length`).
* **Port 80 (TCP)**: HTTP Nginx Web Server (`nginx/1.15.7`).
* **Port 22 (TCP)**: SSH Server (`OpenSSH_7.9` embedded Linux).
* Port 554 / 8554 (RTSP): **TUTUP** (Tidak digunakan).
* Port 1883 / 8883 (MQTT): **TUTUP**.

---

## 3. Mekanisme Persistent Group & Bug Reinvoke

### Karakteristik Desay SV Firmware:
Headunit Desay SV menyimpan kredensial pemasangan (pairing credentials) smartphone setelah koneksi pertama kali berhasil dilakukan melalui aplikasi resmi. Pada sesi-sesi berikutnya, headunit mengharapkan **Reinvocation dari Grup Persistent** (`connectionType=REINVOKE`), bukan negosiasi baru (`persistent=0`).

### Masalah `Dropping connect request`:
Di Android:
1. Jika smartphone **sudah terhubung** ke grup P2P (`p2p-wlan0-0` sudah aktif dan memiliki IP `192.168.2.145`), pemanggilan `WifiP2pManager.connect()` akan **ditolak secara internal** oleh sistem (`E WifiP2pService: Dropping connect request`).
2. Namun `ActionListener.onSuccess()` di aplikasi tetap terpanggil (karena IPC berhasil terkirim).
3. Karena sambungan sudah terbentuk sebelum aplikasi dibuka, event `WIFI_P2P_CONNECTION_CHANGED_ACTION` tidak ditembakkan ulang oleh Android.

### Solusi Desain Aplikasi:
* Saat inisialisasi / startup aplikasi, **wajib** memanggil `WifiP2pManager.requestConnectionInfo()` dan `requestGroupInfo()`.
* Jika `info.groupFormed == true`, aplikasi harus langsung menandai status `CONNECTED` dan mengambil `192.168.2.1` tanpa memanggil `connect()` lagi.
* Jika koneksi terputus atau perlu diulang, panggil `WifiP2pManager.removeGroup()` untuk mereset sesi.
