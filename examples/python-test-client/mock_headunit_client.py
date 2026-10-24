#!/usr/bin/env python3
"""
OMOWAY Headunit Test & Probe Client
===================================
Skrip utilitas Python untuk menguji koneksi kontrol (Port 9527) dan video (Port 9528)
ke cluster motor listrik OMOWAY (192.168.2.1).

Cara Penggunaan:
    python mock_headunit_client.py [TARGET_IP]
    Default IP: 192.168.2.1
"""

import sys
import socket
import struct
import time
import threading

TARGET_IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.2.1"
CTRL_PORT = 9527
VIDEO_PORT = 9528

def run_control_client():
    print(f"[*] Menghubungkan ke Saluran Kontrol ({TARGET_IP}:{CTRL_PORT})...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((TARGET_IP, CTRL_PORT))
        s.settimeout(None)
        print(f"[+] Terhubung ke Saluran Kontrol Port {CTRL_PORT}!")
    except Exception as e:
        print(f"[-] Gagal terhubung ke Port {CTRL_PORT}: {e}")
        return

    def send_pkt(channel_id, msg_id, body=b""):
        plen = 2 + len(body)
        hdr = struct.pack("<IIH", channel_id, plen, msg_id)
        try:
            s.sendall(hdr + body)
        except Exception as err:
            print(f"[-] Send error: {err}")

    # Kirim status inisialisasi awal
    init_json = b'{"msg_id":"DS_MSG_PHONE_STATUS","status":"READY","stream_port":9528,"version":"1.0"}'
    send_pkt(1, 0x0001, init_json)

    while True:
        try:
            hdr = s.recv(8)
            if len(hdr) < 8:
                print("[-] Saluran Kontrol ditutup oleh remote.")
                break
            channel_id, plen = struct.unpack("<II", hdr)
            payload = b""
            while len(payload) < plen:
                chunk = s.recv(plen - len(payload))
                if not chunk:
                    break
                payload += chunk

            if len(payload) >= 2:
                msg_id = struct.unpack("<H", payload[:2])[0]
                body = payload[2:]
                now = time.strftime("%H:%M:%S")

                if msg_id == 9:
                    # Heartbeat Ping dari Speedometer Motor -> Balas Pong 10
                    send_pkt(1, 10, body)
                    # print(f"[{now}] [Ch 1] Ping 9 -> Pong 10")
                elif msg_id == 37:
                    # Day / Night mode -> Berikan ACK
                    text = body.decode('utf-8', errors='ignore')
                    print(f"[{now}] [Ch 7] Mode Motor: {text}")
                    send_pkt(7, 37, b'{"result":0}')
                elif msg_id == 0x31:
                    print(f"[{now}] [Ch 1] Handshake Kunci Motor Diterima (Len: {len(body)})")
                else:
                    text = body.decode('utf-8', errors='ignore')
                    print(f"[{now}] [Ch {channel_id}] Pesan Masuk (Msg {msg_id}): {text}")

                    if "DS_MSG_HU_REQ_SHOW" in text:
                        print("★ SPEEDOMETER MEMINTA TAMPILAN AKTIF (DS_MSG_HU_REQ_SHOW)!")
                        ack = b'{"msg_id":"DS_RESP_SHOW","result":0,"status":"STREAMING"}'
                        send_pkt(1, 0x0002, ack)
        except Exception as e:
            print(f"[-] Kontrol exception: {e}")
            break

    s.close()

def run_video_probe():
    time.sleep(1)
    print(f"[*] Menguji koneksi Saluran Video ({TARGET_IP}:{VIDEO_PORT})...")
    try:
        vs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        vs.settimeout(3.0)
        vs.connect((TARGET_IP, VIDEO_PORT))
        print(f"[+] Terhubung ke Saluran Video Port {VIDEO_PORT}!")
        # Soket siap menerima NALU H.264
        vs.close()
    except Exception as e:
        print(f"[-] Video port probe gagal: {e}")

if __name__ == "__main__":
    t_vid = threading.Thread(target=run_video_probe, daemon=True)
    t_vid.start()
    run_control_client()
