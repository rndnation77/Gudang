import os
import time
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
import pandas as pd
import openpyxl
import io
import json

# Import lokal
from database import SessionLocal, engine, Base
from models import Gudang, Rak, Toples, Aktifitas, Barang

app = Flask(__name__)

# --- KONFIGURASI ---
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Inisialisasi Database & Folder
Base.metadata.create_all(bind=engine)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- HELPER FUNCTIONS ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_foto(file):
    if file and allowed_file(file.filename):
        ts = int(time.time())
        filename = secure_filename(f"{ts}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None

# --- ROUTES: UTAMA & MASTER ---

import json

@app.route('/')
def index():
    db = SessionLocal()
    search = request.args.get('search', '')
    gudang_id = request.args.get('gudang_id')
    rak_id = request.args.get('rak_id')
    toples_id = request.args.get('toples_id')

    try:
        # 1. Query Barang dengan Eager Loading (Mengambil semua relasi sekaligus)
        # Sesuai model: Barang -> toples -> rak -> gudang
        query = db.query(Barang).options(
            joinedload(Barang.toples)
            .joinedload(Toples.rak)
            .joinedload(Rak.gudang)
        )

        # 2. Logika Filter Pencarian Nama/SKU
        if search:
            query = query.filter(
                (Barang.nama_barang.ilike(f"%{search}%")) | 
                (Barang.kode_barang.ilike(f"%{search}%"))
            )

        # 3. Logika Filter Lokasi (Join diperlukan agar bisa filter kolom di tabel lain)
        if toples_id:
            query = query.filter(Barang.toples_id == toples_id)
        elif rak_id:
            query = query.join(Toples).filter(Toples.rak_id == rak_id)
        elif gudang_id:
            query = query.join(Toples).join(Rak).filter(Rak.gudang_id == gudang_id)

        barang_list = query.all()

        # 4. Ambil Data Gudang & Struktur untuk Dropdown JS
        # Kita ambil raks dan toples_list sesuai nama attribute di model kamu
        gudangs = db.query(Gudang).options(
            joinedload(Gudang.raks).joinedload(Rak.toples_list)
        ).all()

        # Konversi ke JSON agar JavaScript di HTML bisa memproses filter bertingkat
        gudangs_data = []
        for g in gudangs:
            g_item = {"id": g.id, "nama_gudang": g.nama_gudang, "raks": []}
            for r in g.raks:
                r_item = {"id": r.id, "nama_rak": r.nama_rak, "toples_list": []}
                for t in r.toples_list:
                    r_item["toples_list"].append({"id": t.id, "nama_toples": t.nama_toples})
                g_item["raks"].append(r_item)
            gudangs_data.append(g_item)

        return render_template(
            'index.html', 
            barang=barang_list, 
            gudangs=gudangs, 
            gudangs_json=json.dumps(gudangs_data)
        )

    finally:
        db.close() # Aman ditutup karena data sudah di-load semua lewat joinedload
@app.route('/master-data')
def master_data():
    db = SessionLocal()
    try:
        gudangs = db.query(Gudang).options(
            joinedload(Gudang.raks).joinedload(Rak.toples_list).joinedload(Toples.barangs)
        ).all()
        logs = db.query(Aktifitas).order_by(Aktifitas.id.desc()).limit(15).all()
        return render_template('master_data.html', gudangs=gudangs, logs=logs)
    finally:
        db.close()

# --- ROUTES: CREATE ---

@app.route('/add_gudang', methods=['POST'])
def add_gudang():
    db = SessionLocal()
    nama = request.form.get('nama_gudang')
    if nama:
        db.add(Gudang(nama_gudang=nama))
        db.add(Aktifitas(acara=f"Dibuat Gudang Baru: {nama}"))
        db.commit()
    db.close()
    return redirect(url_for('master_data'))

@app.route('/add_rak/<int:gudang_id>', methods=['POST'])
def add_rak(gudang_id):
    db = SessionLocal()
    nama = request.form.get('nama_rak')
    kode = request.form.get('kode_rak')
    if nama:
        db.add(Rak(nama_rak=nama, kode_rak=kode, gudang_id=gudang_id))
        db.add(Aktifitas(acara=f"Ditambah Rak: {nama} [{kode}]"))
        db.commit()
    db.close()
    return redirect(url_for('master_data'))

@app.route('/add_toples/<int:rak_id>', methods=['POST'])
def add_toples(rak_id):
    db = SessionLocal()
    nama = request.form.get('nama_toples')
    if nama:
        db.add(Toples(nama_toples=nama, rak_id=rak_id))
        db.add(Aktifitas(acara=f"Ditambah Toples: {nama}"))
        db.commit()
    db.close()
    return redirect(url_for('master_data'))

@app.route('/add_barang_inventory', methods=['POST'])
def add_barang_inventory():
    db = SessionLocal()
    nama = request.form.get('nama_barang')
    toples_id = request.form.get('toples_id')
    status = request.form.get('status', 'Tersedia') # Ambil status, default 'Tersedia'
    
    if nama and toples_id:
        filename = save_foto(request.files.get('foto'))
        baru = Barang(
            nama_barang=nama, 
            kode_barang=request.form.get('kode_barang'), 
            status=status,  # Simpan status ke DB
            toples_id=int(toples_id),
            foto_barang=filename 
        )
        db.add(baru)
        db.add(Aktifitas(acara=f"Barang Masuk: {nama} ({status})"))
        db.commit()
    db.close()
    return redirect(url_for('index'))

# --- ROUTES: EDIT & DELETE ---

@app.route('/edit_barang/<int:id>')
def edit_barang_page(id):
    db = SessionLocal()
    try:
        barang = db.get(Barang, id)
        gudangs = db.query(Gudang).options(joinedload(Gudang.raks).joinedload(Rak.toples_list)).all()
        return render_template('edit_barang.html', b=barang, gudangs=gudangs)
    finally:
        db.close()

@app.route('/update_barang/<int:id>', methods=['POST'])
def update_barang(id):
    db = SessionLocal()
    barang = db.get(Barang, id)
    if barang:
        # Update data teks
        barang.nama_barang = request.form.get('nama_barang')
        barang.kode_barang = request.form.get('kode_barang')
        barang.toples_id = int(request.form.get('toples_id'))
        
        # UPDATE STATUS DISINI
        old_status = barang.status
        new_status = request.form.get('status')
        barang.status = new_status
        
        # Proses Foto
        file = request.files.get('foto')
        if file and allowed_file(file.filename):
            if barang.foto_barang:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], barang.foto_barang)
                if os.path.exists(old_path): os.remove(old_path)
            barang.foto_barang = save_foto(file)

        # Catat di Log Aktifitas
        log_msg = f"Update Barang: {barang.nama_barang}"
        if old_status != new_status:
            log_msg += f" (Status: {old_status} -> {new_status})"
            
        db.add(Aktifitas(acara=log_msg))
        db.commit()
    db.close()
    return redirect(url_for('index'))

@app.route('/delete_barang/<int:id>')
def delete_barang(id):
    db = SessionLocal()
    barang = db.get(Barang, id)
    if barang:
        # Hapus foto fisik
        if barang.foto_barang:
            path = os.path.join(app.config['UPLOAD_FOLDER'], barang.foto_barang)
            if os.path.exists(path): os.remove(path)
            
        # Catat log sebelum dihapus
        db.add(Aktifitas(acara=f"Menghapus Barang: {barang.nama_barang} (Kode: {barang.kode_barang})"))
        db.delete(barang)
        db.commit()
    db.close()
    return redirect(url_for('index'))

@app.route('/delete_toples/<int:id>')
def delete_toples(id):
    db = SessionLocal()
    target = db.get(Toples, id)
    if target:
        db.add(Aktifitas(acara=f"Menghapus Toples: {target.nama_toples}"))
        db.delete(target)
        db.commit()
    db.close()
    return redirect(url_for('master_data'))

# --- ROUTES: NAVIGASI BARANG/RAK/TOPLES ---

@app.route('/tambah-barang')
def tambah_barang_page():
    db = SessionLocal()
    try:
        gudangs = db.query(Gudang).options(joinedload(Gudang.raks).joinedload(Rak.toples_list)).all()
        return render_template('tambah_barang.html', gudangs=gudangs)
    finally:
        db.close()

@app.route('/rak/<int:rak_id>')
def kelola_rak(rak_id):
    db = SessionLocal()
    try:
        rak = db.query(Rak).options(joinedload(Rak.gudang), joinedload(Rak.toples_list)).get(rak_id)
        return render_template('kelola_rak.html', rak=rak) if rak else ("Rak tidak ditemukan", 404)
    finally:
        db.close()

@app.route('/toples/<int:toples_id>')
def kelola_toples(toples_id):
    db = SessionLocal()
    try:
        toples = db.query(Toples).options(
            joinedload(Toples.rak).joinedload(Rak.gudang),
            joinedload(Toples.barangs)
        ).get(toples_id)
        return render_template('kelola_toples.html', toples=toples) if toples else ("Toples tidak ditemukan", 404)
    finally:
        db.close()

@app.route('/kelola-semua-rak')
def list_rak():
    db = SessionLocal()
    try:
        raks = db.query(Rak).options(joinedload(Rak.gudang), joinedload(Rak.toples_list)).all()
        return render_template('list_rak.html', raks=raks)
    finally:
        db.close()

@app.route('/kelola-semua-toples')
def list_toples():
    db = SessionLocal()
    try:
        toples = db.query(Toples).options(joinedload(Toples.rak).joinedload(Rak.gudang), joinedload(Toples.barangs)).all()
        return render_template('list_toples.html', toples_list=toples)
    finally:
        db.close()

    
# --- EDIT & UPDATE RAK ---
@app.route('/edit_rak/<int:id>')
def edit_rak_page(id):
    db = SessionLocal()
    rak = db.get(Rak, id)
    gudangs = db.query(Gudang).all()
    db.close()
    return render_template('edit_rak.html', rak=rak, gudangs=gudangs)

@app.route('/update_rak/<int:id>', methods=['POST'])
def update_rak(id):
    db = SessionLocal()
    rak = db.get(Rak, id)
    if rak:
        rak.nama_rak = request.form.get('nama_rak')
        rak.kode_rak = request.form.get('kode_rak')
        rak.gudang_id = int(request.form.get('gudang_id'))
        db.add(Aktifitas(acara=f"Update Rak: {rak.nama_rak}"))
        db.commit()
    db.close()
    return redirect(url_for('master_data'))

# --- EDIT & UPDATE TOPLES ---
@app.route('/edit_toples/<int:id>')
def edit_toples_page(id):
    db = SessionLocal()
    toples = db.get(Toples, id)
    # Ambil semua rak untuk pilihan pindah lokasi
    raks = db.query(Rak).options(joinedload(Rak.gudang)).all()
    db.close()
    return render_template('edit_toples.html', toples=toples, raks=raks)

@app.route('/update_toples/<int:id>', methods=['POST'])
def update_toples(id):
    db = SessionLocal()
    toples = db.get(Toples, id)
    if toples:
        toples.nama_toples = request.form.get('nama_toples')
        toples.rak_id = int(request.form.get('rak_id'))
        db.add(Aktifitas(acara=f"Update Toples: {toples.nama_toples}"))
        db.commit()
    db.close()
    return redirect(url_for('master_data'))

# --- DELETE RAK (Belum ada tadi) ---
@app.route('/delete_rak/<int:id>')
def delete_rak(id):
    db = SessionLocal()
    rak = db.get(Rak, id)
    if rak:
        db.add(Aktifitas(acara=f"Menghapus Rak: {rak.nama_rak}"))
        db.delete(rak)
        db.commit()
    db.close()
    return redirect(url_for('master_data'))


# --- ROUTE UNTUK HALAMAN UPLOAD ---
@app.route('/shopee-upload')
def shopee_upload_page():
    return render_template('shopee_upload.html')

# --- ROUTE UNTUK PROSES MAPPING (Sesuai saran sebelumnya) ---
@app.route('/shopee-importer', methods=['GET', 'POST'])
def shopee_importer():
    db = SessionLocal()
    gudangs = db.query(Gudang).options(joinedload(Gudang.raks).joinedload(Rak.toples_list)).all()
    
    if request.method == 'POST':
        file = request.files.get('file_shopee')
        if not file:
            return "File tidak ditemukan", 400
            
        filename = "temp_import.csv"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            # Baca file sebagai teks untuk deteksi pemisah
            content = file.read().decode("utf-8-sig", errors='ignore')
            
            # CEK PEMISAH: Apakah pakai titik koma (;) atau koma (,)
            # Karena file kamu pakai (;) kita tambahkan sep=None agar pandas otomatis mendeteksi
            df = pd.read_csv(io.StringIO(content), sep=None, engine='python', on_bad_lines='skip')

            # CLEANING: Hapus kolom kosong (Unnamed)
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

            # SIMPAN KE TEMP (Gunakan koma standar untuk tahap berikutnya)
            df.to_csv(filepath, index=False)
            
            # Ambil list header untuk ditampilkan di halaman mapping
            headers = [str(h) for h in df.columns.tolist() if h]

            db.close()
            return render_template('shopee_mapping.html', headers=headers, gudangs=gudangs)

        except Exception as e:
            db.close()
            return f"Gagal membaca file: {str(e)}"
            
    db.close()
    return redirect(url_for('shopee_upload_page'))

@app.route('/process-import', methods=['POST'])
def process_import():
    db = SessionLocal()
    col_nama = request.form.get('map_nama')
    col_sku = request.form.get('map_sku')
    col_foto = request.form.get('map_foto')
    toples_id = request.form.get('toples_id')
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_import.csv')
    
    try:
        df = pd.read_csv(filepath)
        
        # --- OPTIMASI SPEED: Ambil semua SKU yang sudah ada di DB ke dalam Set (RAM) ---
        # Ini jauh lebih cepat daripada query satu-satu di dalam loop
        existing_skus = {s[0] for s in db.query(Barang.kode_barang).all()}
        
        count = 0
        objects_to_add = [] # Kita kumpulkan dulu semua barang baru di sini

        for index, row in df.iterrows():
            nama = row[col_nama]
            if pd.isna(nama): continue

            # 1. Ambil SKU dasar
            sku_raw = row[col_sku] if col_sku in row else None
            sku_base = str(sku_raw).strip() if pd.notna(sku_raw) and str(sku_raw).strip() != "" else "TANPA-SKU"
            
            # 2. Logika Cepat Cari SKU Unik di Memori
            sku_final = sku_base
            suffix = 1
            while sku_final in existing_skus:
                sku_final = f"{sku_base}-{suffix}"
                suffix += 1
            
            # 3. Masukkan SKU baru ke catatan memori agar baris berikutnya tahu
            existing_skus.add(sku_final)
            
            foto = row[col_foto] if col_foto in row else None
            
            # 4. Buat objek barang (tapi jangan simpan ke DB dulu)
            baru = Barang(
                nama_barang=str(nama),
                kode_barang=sku_final,
                foto_barang=str(foto) if pd.notna(foto) else None,
                status="Tersedia",
                jumlah=0,
                toples_id=int(toples_id)
            )
            objects_to_add.append(baru)
            count += 1
        
        # --- SIMPAN MASSAL (Bulk Insert) ---
        # Ini mengirim semua data sekaligus, bukan satu-satu
        db.bulk_save_objects(objects_to_add)
        db.add(Aktifitas(acara=f"Import Turbo: {count} barang masuk."))
        db.commit()
        
    except Exception as e:
        db.rollback()
        return f"Terjadi kesalahan: {str(e)}"
    finally:
        db.close()
        if os.path.exists(filepath):
            os.remove(filepath) 
            
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(debug=True)