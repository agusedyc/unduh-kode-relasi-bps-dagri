import json
import csv
import requests
import time
import undetected_chromedriver as uc

# BPS menggunakan perlindungan Cloudflare Turnstile tingkat tinggi.
# Playwright biasa terdeteksi. Kita gunakan undetected_chromedriver.

import os

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

desa = []
for i in prov:
    url_kab = f"{domain}/rest-bridging/getwilayah?level=kabupaten&parent={i}&periode_merge={periode}"
    res = requests.get(url_kab, headers=headers)
    
    if "One moment, please" in res.text:
        print("\n[ERROR] Sesi terputus/ditolak Cloudflare di tengah jalan.")
        break
        
    try:
        dhtml = res.json()
    except json.JSONDecodeError:
        print("\nGagal baca JSON. Respons BPS:", res.text[:100])
        break

    for j in dhtml:
        url_kec = f"{domain}/rest-bridging/getwilayah?level=kecamatan&parent={j['kode_bps']}&periode_merge={periode}"
        res2 = requests.get(url_kec, headers=headers)
        dhtml2 = res2.json()
        
        for key in list(j.keys()):
            j[key+'_kabkot'] = j.pop(key)
            
        for n in dhtml2:
            print(f"Memproses : {j.get('nama_bps_kabkot', '')}")
            url_desa = f"{domain}/rest-bridging/getwilayah?level=desa&parent={n['kode_bps']}&periode_merge={periode}"
            res3 = requests.get(url_desa, headers=headers)
            dhtml3 = res3.json()
            
            for key in list(n.keys()):
                n[key+'_kec'] = n.pop(key)
            n.update(j)
            
            for k in dhtml3:
                for key in list(k.keys()):
                    k[key+'_deskel'] = k.pop(key)
                k.update(n)
                desa.append(k)
                print(f"Selesai: {j.get('nama_bps_kabkot', '')} | Kec: {n.get('nama_bps_kec', '')} | Desa: {k.get('nama_bps_deskel', '')}")

if len(desa) > 0:
    head = list(desa[0].keys())
    with open('data-relasi-baru.csv', 'w', newline='', encoding='utf-8') as o_f:
        d_w = csv.DictWriter(o_f, head)
        d_w.writeheader()
        d_w.writerows(desa)
    print("Selesai. Data disimpan.")
else:
    print('Tidak ada data desa yang diproses.')
