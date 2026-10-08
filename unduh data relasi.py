import json
import csv
import requests
import time
import undetected_chromedriver as uc
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# BPS menggunakan perlindungan Cloudflare Turnstile tingkat tinggi.
# Playwright biasa terdeteksi. Kita gunakan undetected_chromedriver.

periode = '2025_2.2025'
domain = 'https://sig.bps.go.id'
url_prov = f"{domain}/rest-bridging/getwilayah?level=provinsi&parent=0&periode_merge={periode}"

print("==================================================")
print("Membuka browser Anti-Deteksi (Undetected Chromedriver)...")
print("==================================================")

try:
    options = uc.ChromeOptions()
    
    # Deteksi Brave jika Chrome tidak ada
    brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    if os.path.exists(brave_path):
        options.binary_location = brave_path
        print("Brave Browser terdeteksi.")
        
    driver = uc.Chrome(options=options, version_main=154)
    
    print("Membuka homepage BPS...")
    driver.get('https://sig.bps.go.id/')
    time.sleep(5)
    
    print("Beralih ke endpoint API...")
    driver.get(url_prov)
    
    print("Menunggu Cloudflare selesai memproses...")
    # Tunggu sampai teks json 'kode_bps' muncul di body browser
    timeout = 60
    start_time = time.time()
    while True:
        body_text = driver.execute_script("return document.body.innerText")
        if "kode_bps" in body_text:
            print("\nBerhasil melewati Cloudflare!")
            dhtml_prov = json.loads(body_text)
            break
        if time.time() - start_time > timeout:
            raise Exception("Timeout menunggu Cloudflare (60 detik).")
        time.sleep(1)

    # Ambil Cookie & User-Agent
    selenium_cookies = driver.get_cookies()
    cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in selenium_cookies])
    user_agent = driver.execute_script("return navigator.userAgent;")
    
    driver.quit()

except Exception as e:
    print("\nGagal melewati Cloudflare:", e)
    try: driver.quit() 
    except: pass
    exit(1)

# Lanjut menggunakan requests
headers = {
    'User-Agent': user_agent,
    'Cookie': cookie_string,
    'Accept': 'application/json, text/plain, */*'
}

prov = [p['kode_bps'] for p in dhtml_prov]
print(f"Provinsi ditemukan: {len(prov)}")

def proses_provinsi(kode_prov, headers, periode, domain):
    desa_lokal = []
    url_kab = f"{domain}/rest-bridging/getwilayah?level=kabupaten&parent={kode_prov}&periode_merge={periode}"
    
    try:
        res = requests.get(url_kab, headers=headers, timeout=30)
        if "One moment, please" in res.text:
            print(f"\n[ERROR] Sesi terputus/ditolak Cloudflare di Provinsi {kode_prov}")
            return []
        dhtml = res.json()
    except Exception as e:
        print(f"\nGagal baca Kab/Kot Provinsi {kode_prov}: {e}")
        return []

    for j in dhtml:
        url_kec = f"{domain}/rest-bridging/getwilayah?level=kecamatan&parent={j['kode_bps']}&periode_merge={periode}"
        try:
            res2 = requests.get(url_kec, headers=headers, timeout=30)
            dhtml2 = res2.json()
        except Exception:
            continue
            
        # Rename keys j
        for key in list(j.keys()):
            j[key+'_kabkot'] = j.pop(key)
            
        for n in dhtml2:
            print(f"Memproses : {j.get('nama_bps_kabkot', '')} - Kec: {n.get('nama_bps', '')}")
            url_desa = f"{domain}/rest-bridging/getwilayah?level=desa&parent={n['kode_bps']}&periode_merge={periode}"
            try:
                res3 = requests.get(url_desa, headers=headers, timeout=30)
                dhtml3 = res3.json()
            except Exception:
                continue
                
            # Rename keys n
            for key in list(n.keys()):
                n[key+'_kec'] = n.pop(key)
            
            # Merge kabkot dict ke kec dict
            n.update(j)
            
            for k in dhtml3:
                # Rename keys k
                for key in list(k.keys()):
                    k[key+'_deskel'] = k.pop(key)
                
                # Merge kec dict (n) ke deskel dict (k)
                k.update(n)
                desa_lokal.append(k.copy())
                
    print(f"--- Selesai Provinsi {kode_prov}: {len(desa_lokal)} desa diproses ---")
    return desa_lokal

desa = []
print("\nMemulai proses unduh secara paralel (10 Provinsi bersamaan)...")
# Gunakan 10 thread (max_workers=10)
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(proses_provinsi, p, headers, periode, domain) for p in prov]
    
    for future in as_completed(futures):
        hasil = future.result()
        if hasil:
            desa.extend(hasil)

if len(desa) > 0:
    head = list(desa[0].keys())
    with open('data-relasi-baru.csv', 'w', newline='', encoding='utf-8') as o_f:
        d_w = csv.DictWriter(o_f, head)
        d_w.writeheader()
        d_w.writerows(desa)
    print(f"\nSelesai. Total {len(desa)} Data disimpan ke data-relasi-baru.csv")
else:
    print('\nTidak ada data desa yang diproses.')
