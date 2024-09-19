from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import Database
from bson.objectid import ObjectId
from datetime import datetime
import os
import uuid
import config

app = Flask(__name__)
app.secret_key = 'secret_key'
app.jinja_env.filters['format_currency'] = lambda value: "Rp {:,.0f}".format(float(value))
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS

# Koneksi ke database
db = Database(config.MONGO_DB)

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' not in session:
        if request.method == 'POST':
            data = request.json
            username = data['username']
            password = data['password']
            user = db.find_one(config.MONGO_USERS_COLLECTION, {'username': username})
            
            if user['status'] and check_password_hash(user['data']['password'], password):
                session['username'] = username
                session['user_id'] = str(user['data']['_id'])
                return jsonify({'message': 'Login Successful.', 'redirect_url': url_for('dashboard')}), 200
            else:
                return jsonify({'message': 'Username atau Password Salah !.'}), 401
        return render_template('login.html')
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    if 'username' in session:
        session.pop('username', None)
        session.pop('user_id', None)
        return jsonify({'message': 'Logout Successful.', 'redirect_url': url_for('login')}), 200
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data['username']
        password = data['password']
        karyawan_id = data['karyawan']

        usernames = db.find_one(config.MONGO_USERS_COLLECTION, {'username': username})
        if usernames['status']:
            return jsonify({'message': 'Username sudah ada.'}), 400
        
        id = db.find_one(config.MONGO_USERS_COLLECTION, {'karyawan_id': karyawan_id})
        if id['status']:
            return jsonify({'message': 'Akun sudah ada.'}), 400

        hashed_password = generate_password_hash(password)
        result = db.insert_one(config.MONGO_USERS_COLLECTION, {
            'username': username, 
            'password': hashed_password, 
            'karyawan_id': karyawan_id
        })
        if result['status']:
            return jsonify({'message': 'Registrasi berhasil.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat registrasi.'}), 500

    # Ambil daftar karyawan dari database
    karyawan_data = db.find_all(config.MONGO_KARYAWAN_COLLECTION)
    if karyawan_data['status']:
        karyawan_data = karyawan_data['data']
    else:
        karyawan_data = []

    return render_template('register.html', karyawan_data=karyawan_data)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Ambil ID karyawan dari session
    user_id = session['user_id']
    user = db.find_one(config.MONGO_USERS_COLLECTION, {'_id': ObjectId(user_id)})
    
    if user['status']:
        # Ambil data karyawan by id
        karyawan_id = user['data']['karyawan_id']
        karyawan = db.find_one(config.MONGO_KARYAWAN_COLLECTION, {'_id': ObjectId(karyawan_id)})
        if karyawan['status']:
            karyawan_name = karyawan['data']['nama_lengkap']
            return render_template('dashboard.html', karyawan_name=karyawan_name)
        else:
            return render_template('dashboard.html', karyawan_name='')
    else:
        return render_template('dashboard.html', karyawan_name='')

@app.route('/karyawan', methods=['GET'])
def karyawan():
    result = db.find_all(config.MONGO_KARYAWAN_COLLECTION)
    if result['status']:
        karyawans = result['data']
    else:
        karyawans = []
    return render_template('list_karyawan.html', karyawans=karyawans)

@app.route('/tambah_karyawan', methods=['GET'])
def tambah_karyawan():
    return render_template('tambah_karyawan.html')

@app.route('/add_karyawan', methods=['POST'])
def add_karyawan():
    if 'foto_profil' not in request.files:
        return jsonify({'message': 'Tidak ada file yang diunggah.'}), 400

    file = request.files['foto_profil']

    if file.filename == '':
        return jsonify({'message': 'Nama file kosong.'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    else:
        return jsonify({'message': 'File tidak diizinkan.'}), 400

    data = {
        'nama_lengkap': request.form['nama_lengkap'],
        'email': request.form['email'],
        'nomor_telepon': request.form['nomor_telepon'],
        'tanggal_bergabung': request.form['tanggal_bergabung'],
        'posisi': request.form['posisi'],
        'gaji': request.form['gaji'],
        'foto_profil': filename
    }

    result = db.insert_one(config.MONGO_KARYAWAN_COLLECTION, data)

    if result['status']:
        return jsonify({'message': 'Karyawan berhasil ditambahkan.'}), 200
    else:
        return jsonify({'message': 'Gagal menambahkan karyawan.'}), 500

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/update_karyawan/<id>', methods=['POST'])
def update_karyawan(id):
    try:
        data = request.form.to_dict()
        karyawan = db.find_one(config.MONGO_KARYAWAN_COLLECTION, {'_id': ObjectId(id)})
        if karyawan['status']:
            karyawan_data = karyawan['data']
        else:
            return jsonify({'message': 'Karyawan not found'}), 404

        if 'foto_profil' in request.files:
            foto_profil = request.files['foto_profil']
            if foto_profil and allowed_file(foto_profil.filename):
                filename = secure_filename(foto_profil.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                foto_profil.save(filepath)
                data['foto_profil'] = filepath

                # Delete the old photo if it exists and is different
                if 'foto_profil' in karyawan_data and karyawan_data['foto_profil'] != filepath:
                    old_filepath = karyawan_data['foto_profil']
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)

        result = db.update_one(config.MONGO_KARYAWAN_COLLECTION, {'_id': ObjectId(id)}, {'foto_profil': data})
        if result['status']:
            return jsonify({'message': 'Karyawan updated successfully!'}), 200
        else:
            return jsonify({'message': result['message']}), 400

    except Exception as e:
        return jsonify({'message': str(e)}), 400


@app.route('/delete_karyawan/<id>', methods=['DELETE'])
def delete_karyawan(id):
    try:
        karyawan = db.find_one(config.MONGO_KARYAWAN_COLLECTION, {'_id': ObjectId(id)})
        if karyawan['status']:
            karyawan_data = karyawan['data']
        else:
            return jsonify({'message': 'Karyawan not found'}), 404

        # Delete the profile photo if it exists
        if 'foto_profil' in karyawan_data:
            foto_profil_path = karyawan_data['foto_profil']
            if os.path.exists(foto_profil_path):
                os.remove(foto_profil_path)

        result = db.delete_one(config.MONGO_KARYAWAN_COLLECTION, {'_id': ObjectId(id)})
        if result['status']:
            return jsonify({'message': 'Karyawan deleted successfully!'}), 200
        else:
            return jsonify({'message': result['message']}), 400
    except Exception as e:
        return jsonify({'message': str(e)}), 400


    
@app.route('/kategori')
def kategori():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    search_field = 'nama_kategori'

    result = db.find_all(config.MONGO_KATEGORI_COLLECTION, page=page, per_page=per_page, search_query=search_query, search_field=search_field)
    
    if result['status']:
        kategori_data = result['data']
        total_kategori = result['total_documents']
    else:
        kategori_data = []
        total_kategori = 0

    return render_template('kategori.html', kategori_data=kategori_data, page=page, per_page=per_page, total_kategori=total_kategori, search=search_query)

#Kategori
@app.route('/get_total_kategori', methods=['GET'])
def get_total_kategori():
    total_kategori = db.count_documents(config.MONGO_KATEGORI_COLLECTION)
    return jsonify({'total_kategori': total_kategori}), 200

@app.route('/kategori/tambah', methods=['POST'])
def tambah_kategori():
    if request.method == 'POST':
        data = request.json
        nama_kategori = data['namaKategori']

        # Pengecekan Duplikasi Nama
        existing_kategori = db.find_one(config.MONGO_KATEGORI_COLLECTION, {'nama_kategori': nama_kategori})
        if existing_kategori['status']:
            return jsonify({'message': 'Kategori dengan nama tersebut sudah ada.'}), 400

        result = db.insert_one(config.MONGO_KATEGORI_COLLECTION, {'nama_kategori': nama_kategori})
        
        if result['status']:
            return jsonify({'message': 'Kategori berhasil ditambahkan.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat menambahkan kategori.'}), 500


@app.route('/kategori/update/<kategori_id>', methods=['POST'])
def update_kategori(kategori_id):
    if request.method == 'POST':
        data = request.json
        nama_kategori_baru = data['nama_kategori']

        # Perbarui nama kategori dalam database
        result = db.update_one(config.MONGO_KATEGORI_COLLECTION, {'_id': ObjectId(kategori_id)}, {'nama_kategori': nama_kategori_baru})
        
        if result['status']:
            return jsonify({'message': 'Kategori berhasil diperbarui.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat memperbarui kategori.'}), 500
        
@app.route('/kategori/hapus/<kategori_id>', methods=['GET'])
def hapus_kategori(kategori_id):
    result = db.delete_one(config.MONGO_KATEGORI_COLLECTION, {'_id': ObjectId(kategori_id)})
    if result['status']:
        return jsonify({'message': 'Kategori berhasil dihapus.'}), 200
    else:
        return jsonify({'message': 'Terjadi kesalahan saat menghapus kategori.'}), 500
    
#Brand
@app.route('/get_total_brand', methods=['GET'])
def get_total_brand():
    total_brand = db.count_documents(config.MONGO_BRAND_COLLECTION)
    return jsonify({'total_brand': total_brand}), 200

@app.route('/brand')
def brand():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    search_field = 'nama_brand'

    result = db.find_all(config.MONGO_BRAND_COLLECTION, page=page, per_page=per_page, search_query=search_query, search_field=search_field)
    
    if result['status']:
        brand_data = result['data']
        total_brand = result['total_documents']
    else:
        brand_data = []
        total_brand = 0

    return render_template('brand.html', brand_data=brand_data, page=page, per_page=per_page, total_brand=total_brand, search=search_query)


@app.route('/brand/tambah', methods=['POST'])
def tambah_brand():
    if request.method == 'POST':
        data = request.json
        nama_brand = data['namabrand']

        # Pengecekan Duplikasi Nama
        existing_brand = db.find_one(config.MONGO_BRAND_COLLECTION, {'nama_brand': nama_brand})
        if existing_brand['status']:
            return jsonify({'message': 'Brand dengan nama tersebut sudah ada.'}), 400

        result = db.insert_one(config.MONGO_BRAND_COLLECTION, {'nama_brand': nama_brand})
        
        if result['status']:
            return jsonify({'message': 'Brand berhasil ditambahkan.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat menambahkan brand.'}), 500


@app.route('/brand/update/<brand_id>', methods=['POST'])
def update_brand(brand_id):
    if request.method == 'POST':
        data = request.json
        nama_brand_baru = data['nama_brand']

        # Perbarui nama brand
        result = db.update_one(config.MONGO_BRAND_COLLECTION, {'_id': ObjectId(brand_id)}, {'nama_brand': nama_brand_baru})
        
        if result['status']:
            return jsonify({'message': 'Brand berhasil diperbarui.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat memperbarui brand.'}), 500
        
@app.route('/brand/hapus/<brand_id>', methods=['GET'])
def hapus_brand(brand_id):
    result = db.delete_one(config.MONGO_BRAND_COLLECTION, {'_id': ObjectId(brand_id)})
    if result['status']:
        return jsonify({'message': 'Brand berhasil dihapus.'}), 200
    else:
        return jsonify({'message': 'Terjadi kesalahan saat menghapus brand.'}), 500


# Produk
@app.route('/get_total_produk', methods=['GET'])
def get_total_produk():
    total_produk = db.count_documents(config.MONGO_PRODUK_COLLECTION)
    return jsonify({'total_produk': total_produk}), 200

@app.route('/produk')
def produk():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    search_field = 'nama_produk'

    result = db.find_all(config.MONGO_PRODUK_COLLECTION, page=page, per_page=per_page, search_query=search_query, search_field=search_field)
    
    if result['status']:
        produk_data = result['data']
        total_produk = result['total_documents']
    else:
        produk_data = []
        total_produk = 0

    kategori_data = db.find_all(config.MONGO_KATEGORI_COLLECTION)
    brand_data = db.find_all(config.MONGO_BRAND_COLLECTION)

    return render_template('produk.html', produk_data=produk_data, kategori_data=kategori_data['data'], brand_data=brand_data['data'], page=page, per_page=per_page, total_produk=total_produk, search=search_query)

@app.route('/produk/tambah', methods=['POST'])
def tambah_produk():
    data = request.json
    if not data:
        return jsonify({'status': False, 'message': 'Tidak ada data yang dikirim'}), 400

    required_fields = ['kode_produk', 'nama_produk', 'kategori_nama', 'brand_nama', 'harga_beli', 'harga_jual', 'stok']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        return jsonify({'status': False, 'message': f'Field berikut harus diisi: {", ".join(missing_fields)}'}), 400

    kode_produk = data['kode_produk']
    nama_produk = data['nama_produk']
    kategori_nama = data['kategori_nama']
    brand_nama = data['brand_nama']
    harga_beli = data['harga_beli']
    harga_jual = data['harga_jual']
    diskon = data.get('diskon', 0)  # Value default  0
    stok = data['stok']

    produk_data = {
        'kode_produk': kode_produk,
        'nama_produk': nama_produk,
        'kategori_nama': kategori_nama,
        'brand_nama': brand_nama,
        'harga_beli': harga_beli,
        'harga_jual': harga_jual,
        'diskon': diskon,
        'stok': stok
    }

    try:
        # Masukkan data produk ke database
        result = db.insert_one(config.MONGO_PRODUK_COLLECTION, produk_data)
        return jsonify(result), 201 if result['status'] else 400
    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500



@app.route('/produk/update/<produk_id>', methods=['POST'])
def update_produk(produk_id):
    if request.method == 'POST':
        data = request.json
        update_data = {
            'nama_produk': data['nama_produk'],
            'kategori_nama': data['kategori_nama'],
            'brand_nama': data['brand_nama'],
            'harga_beli': data['harga_beli'],
            'harga_jual': data['harga_jual'],
            'diskon': data['diskon'],
            'stok': data['stok']
        }

        result = db.update_one(config.MONGO_PRODUK_COLLECTION, {'_id': ObjectId(produk_id)}, update_data)
        
        if result['status']:
            return jsonify({'message': 'Produk berhasil diperbarui.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat memperbarui produk.'}), 500


@app.route('/produk/hapus/<produk_id>', methods=['DELETE'])
def hapus_produk(produk_id):
    result = db.delete_one(config.MONGO_PRODUK_COLLECTION, {'_id': ObjectId(produk_id)})
    if result['status']:
        return jsonify({'message': 'Produk berhasil dihapus.'}), 200
    else:
        return jsonify({'message': 'Terjadi kesalahan saat menghapus produk.'}), 500


@app.route('/produk/generate_kode', methods=['POST'])
def generate_kode_produk():
    data = request.json
    if not data or 'kategori_nama' not in data or 'brand_nama' not in data:
        return jsonify({'status': False, 'message': 'Nama kategori atau merek tidak ditemukan'}), 400

    kategori_nama = data['kategori_nama']
    brand_nama = data['brand_nama']

    brand_code = brand_nama[:3].upper()
    kategori_code = kategori_nama[:3].upper()

    kode_produk = f"{brand_code}{kategori_code}-{generate_nomor_urut()}"

    return jsonify({'status': True, 'kode_produk': kode_produk})


def generate_nomor_urut():
    return str(uuid.uuid4().int)[:3]

#Membership
@app.route('/get_total_member', methods=['GET'])
def get_total_member():
    total_member = db.count_documents(config.MONGO_MEMBERSHIP_COLLECTION)
    return jsonify({'total_member': total_member}), 200

@app.route('/membership')
def membership():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    search_field = 'nama_member'

    result = db.find_all(config.MONGO_MEMBERSHIP_COLLECTION, page=page, per_page=per_page, search_query=search_query, search_field=search_field)
    
    if result['status']:
        membership_data = result['data']
        total_membership = result['total_documents']
    else:
        membership_data = []
        total_membership = 0

    return render_template('membership.html', membership_data=membership_data, page=page, per_page=per_page, total_membership=total_membership, search=search_query)

@app.route('/membership/tambah', methods=['POST'])
def tambah_membership():
    data = request.json
    if not data:
        return jsonify({'status': False, 'message': 'Tidak ada data yang dikirim'}), 400

    required_fields = ['kode_member', 'nama_member', 'alamat', 'no_telepon']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        return jsonify({'status': False, 'message': f'Field berikut harus diisi: {", ".join(missing_fields)}'}), 400

    kode_member = data['kode_member']
    nama_member = data['nama_member']
    alamat = data['alamat']
    no_telepon = data['no_telepon']

    produk_data = {
        'kode_member': kode_member,
        'nama_member': nama_member,
        'alamat': alamat,
        'no_telepon': no_telepon,
    }

    try:
        result = db.insert_one(config.MONGO_MEMBERSHIP_COLLECTION, produk_data)
        return jsonify(result), 201 if result['status'] else 400
    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500


@app.route('/membership/update/<membership_id>', methods=['POST'])
def update_membership(membership_id):
    if request.method == 'POST':
        data = request.json
        update_data = {
            'nama_member': data['nama_member'],
            'alamat': data['alamat'],
            'no_telepon': data['no_telepon'],
        }

        result = db.update_one(config.MONGO_MEMBERSHIP_COLLECTION, {'_id': ObjectId(membership_id)}, update_data)
        
        if result['status']:
            return jsonify({'message': 'Membership berhasil diperbarui.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat memperbarui produk.'}), 500
        
@app.route('/membership/hapus/<membership_id>', methods=['GET'])
def hapus_membership(membership_id):
    result = db.delete_one(config.MONGO_MEMBERSHIP_COLLECTION, {'_id': ObjectId(membership_id)})
    if result['status']:
        return jsonify({'message': 'Member berhasil dihapus.'}), 200
    else:
        return jsonify({'message': 'Terjadi kesalahan saat menghapus membership.'}), 500
    
#Supplier
@app.route('/get_total_supplier', methods=['GET'])
def get_total_supplier():
    total_supplier = db.count_documents(config.MONGO_SUPPLIER_COLLECTION)
    return jsonify({'total_supplier': total_supplier}), 200

@app.route('/supplier')
def supplier():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    search_field = 'nama_supplier'

    result = db.find_all(config.MONGO_SUPPLIER_COLLECTION, page=page, per_page=per_page, search_query=search_query, search_field=search_field)
    
    if result['status']:
        supplier_data = result['data']
        total_supplier = result['total_documents']
    else:
        supplier_data = []
        total_supplier = 0

    return render_template('supplier.html', supplier_data=supplier_data, page=page, per_page=per_page, total_supplier=total_supplier, search=search_query)

@app.route('/supplier/tambah', methods=['POST'])
def tambah_supplier():
    data = request.json
    if not data:
        return jsonify({'status': False, 'message': 'Tidak ada data yang dikirim'}), 400

    required_fields = ['nama_supplier', 'alamat', 'no_telepon']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        return jsonify({'status': False, 'message': f'Field berikut harus diisi: {", ".join(missing_fields)}'}), 400

    nama_supplier = data['nama_supplier']
    alamat = data['alamat']
    no_telepon = data['no_telepon']

    produk_data = {
        'nama_supplier': nama_supplier,
        'alamat': alamat,
        'no_telepon': no_telepon,
    }

    try:
        result = db.insert_one(config.MONGO_SUPPLIER_COLLECTION, produk_data)
        return jsonify(result), 201 if result['status'] else 400
    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500


@app.route('/supplier/update/<supplier_id>', methods=['POST'])
def update_supplier(supplier_id):
    if request.method == 'POST':
        data = request.json
        update_data = {
            'nama_supplier': data['nama_supplier'],
            'alamat': data['alamat'],
            'no_telepon': data['no_telepon'],
        }

        result = db.update_one(config.MONGO_SUPPLIER_COLLECTION, {'_id': ObjectId(supplier_id)}, update_data)
        
        if result['status']:
            return jsonify({'message': 'Produk berhasil diperbarui.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat memperbarui produk.'}), 500
        
@app.route('/supplier/hapus/<supplier_id>', methods=['GET'])
def hapus_supplier(supplier_id):
    result = db.delete_one(config.MONGO_SUPPLIER_COLLECTION, {'_id': ObjectId(supplier_id)})
    if result['status']:
        return jsonify({'message': 'Kategori berhasil dihapus.'}), 200
    else:
        return jsonify({'message': 'Terjadi kesalahan saat menghapus supplier.'}), 500
    
# Pengeluaran
@app.route('/pengeluaran')
def pengeluaran():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    search_field = 'jenis_pengeluaran'

    result = db.find_all(config.MONGO_PENGELUARAN_COLLECTION, page=page, per_page=per_page, search_query=search_query, search_field=search_field)
    
    if result['status']:
        pengeluaran_data = result['data']
        total_pengeluaran = result['total_documents']
    else:
        pengeluaran_data = []
        total_pengeluaran = 0

    return render_template('pengeluaran.html', pengeluaran_data=pengeluaran_data, page=page, per_page=per_page, total_pengeluaran=total_pengeluaran, search=search_query)

@app.route('/pengeluaran/tambah', methods=['POST'])
def tambah_pengeluaran():
    data = request.json
    if not data:
        return jsonify({'status': False, 'message': 'Tidak ada data yang dikirim'}), 400

    required_fields = ['jenis_pengeluaran', 'tanggal', 'nominal']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        return jsonify({'status': False, 'message': f'Field berikut harus diisi: {", ".join(missing_fields)}'}), 400

    jenis_pengeluaran = data['jenis_pengeluaran']
    tanggal = data['tanggal']
    nominal = data['nominal']

    pengeluaran_data = {
        'jenis_pengeluaran': jenis_pengeluaran,
        'tanggal': tanggal,
        'nominal': nominal,
    }

    try:
        result = db.insert_one(config.MONGO_PENGELUARAN_COLLECTION, pengeluaran_data)
        return jsonify(result), 201 if result['status'] else 400
    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500


@app.route('/pengeluaran/update/<pengeluaran_id>', methods=['POST'])
def update_pengeluaran(pengeluaran_id):
    if request.method == 'POST':
        data = request.json
        update_data = {
            'jenis_pengeluaran': data['jenis_pengeluaran'],
            'tanggal': data['tanggal'],
            'nominal': data['nominal'],
        }

        result = db.update_one(config.MONGO_PENGELUARAN_COLLECTION, {'_id': ObjectId(pengeluaran_id)}, update_data)
        
        if result['status']:
            return jsonify({'message': 'Produk berhasil diperbarui.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat memperbarui pengeluaran.'}), 500
        
@app.route('/pengeluaran/hapus/<pengeluaran_id>', methods=['GET'])
def hapus_pengeluaran(pengeluaran_id):
    result = db.delete_one(config.MONGO_PENGELUARAN_COLLECTION, {'_id': ObjectId(pengeluaran_id)})
    if result['status']:
        return jsonify({'message': 'Kategori berhasil dihapus.'}), 200
    else:
        return jsonify({'message': 'Terjadi kesalahan saat menghapus pengeluaran.'}), 500
    
# Pembelian
@app.route('/pembelian', methods=['GET'])
def pembelian():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    search_field = 'supplier'

    result = db.find_all(config.MONGO_PEMBELIAN_COLLECTION, page=page, per_page=per_page, search_query=search_query, search_field=search_field)
    
    if result['status']:
        pembelian_data = result['data']
        total_pembelian = result['total_documents']
    else:
        pembelian_data = []
        total_pembelian = 0

    suppliers_result = db.find_all(config.MONGO_SUPPLIER_COLLECTION, page=1, per_page=0)
    if suppliers_result['status']:
        suppliers = suppliers_result['data']
    else:
        suppliers = []

    products_result = db.find_all(config.MONGO_PRODUK_COLLECTION, page=1, per_page=0)
    if products_result['status']:
        products = products_result['data']
    else:
        products = []

    return render_template('pembelian.html', 
                           pembelian_data=pembelian_data, 
                           page=page, 
                           per_page=per_page, 
                           total_pembelian=total_pembelian, 
                           search=search_query,
                           suppliers=suppliers,
                           products=products,
                           )

@app.route('/pembelian/tambah', methods=['POST'])
def tambah_pembelian():
    data = request.get_json()
    if not data:
        return jsonify({'status': False, 'message': 'Tidak ada data yang dikirim'}), 400

    try:
        pembelian_data = {
            'id_transaksi': data['id_transaksi'],
            'tanggal': data['tanggal'],
            'supplier': data['supplier'],
            'total_item': int(data['total_item']),
            'total_harga': int(data['total_harga']),
            'diskon': int(data['diskon']),
            'total_bayar': int(data['total_bayar'])
        }

        result_pembelian = db.insert_one(config.MONGO_PEMBELIAN_COLLECTION, pembelian_data)
        if not result_pembelian['status']:
            return jsonify({'status': False, 'message': 'Gagal menambahkan pembelian'}), 400

        return jsonify({'status': True, 'message': 'Pembelian berhasil ditambahkan'}), 201

    except (ValueError, KeyError) as e:
        return jsonify({'status': False, 'message': f'Kesalahan input data: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'status': False, 'message': str(e)}), 500



@app.route('/pembelian/update/<pembelian_id>', methods=['POST'])
def update_pembelian(pembelian_id):
    data = request.form
    try:
        update_data = {
            'tanggal': data['editTanggal'],
            'supplier': data['editSupplier'],
            'total_item': int(data['edittotal_item']),
            'total_harga': int(data['edittotal_harga']),
            'diskon': float(data['editdiskon']),
            'total_bayar': int(data['edittotal_bayar'])
        }
    except (ValueError, KeyError) as e:
        return jsonify({'status': False, 'message': f'Kesalahan input data: {str(e)}'}), 400

    result = db.update_one(config.MONGO_PEMBELIAN_COLLECTION, {'_id': ObjectId(pembelian_id)}, update_data)
    
    if result['status']:
        return jsonify({'status': True, 'message': 'Pembelian berhasil diperbarui.'}), 200
    else:
        return jsonify({'status': False, 'message': 'Terjadi kesalahan saat memperbarui pembelian.'}), 500

@app.route('/pembelian/hapus/<pembelian_id>', methods=['DELETE'])
def hapus_pembelian(pembelian_id):
    result = db.delete_one(config.MONGO_PEMBELIAN_COLLECTION, {'_id': ObjectId(pembelian_id)})
    if result['status']:
        return jsonify({'status': True, 'message': 'Pembelian berhasil dihapus.'}), 200
    else:
        return jsonify({'status': False, 'message': 'Terjadi kesalahan saat menghapus pembelian.'}), 500
    
@app.route('/detail_pembelian/<id_transaksi>', methods=['GET'])
def detail_pembelian(id_transaksi):
    print(id_transaksi)
    transaksi_pembelian = db.find_one(config.MONGO_PEMBELIAN_COLLECTION, {'id_transaksi': id_transaksi})
    if not transaksi_pembelian['status']:
        return jsonify({'message': 'Pembelian tidak ditemukan'}), 404
    
    detail_pembelian = db.find_all(config.MONGO_DETAIL_PEMBELIAN_COLLECTION, search_query=id_transaksi, search_field='id_transaksi')

    if detail_pembelian['status']:
        return jsonify(detail_pembelian['data'])
    else:
        return jsonify({'message': 'Detail pembelian tidak ditemukan'}), 404


@app.route('/tambah_detail_pembelian', methods=['POST'])
def tambah_detail_pembelian():
    data = request.get_json()
    collection_name = config.MONGO_DETAIL_PEMBELIAN_COLLECTION

    if not isinstance(data, list):
        return jsonify({'message': 'Data yang dikirim tidak valid'}), 400

    try:
        for detail in data:
            produk_kode = detail.get('produk_kode')
            jumlah_dibeli = detail.get('jumlah')

            if produk_kode is None or jumlah_dibeli is None:
                return jsonify({'message': 'Kode produk atau jumlah tidak ada dalam data'}), 400

            filter_produk = {'kode_produk': produk_kode} 
            produk_result = db.find_one(config.MONGO_PRODUK_COLLECTION, filter_produk)

            if produk_result['status']:
                produk = produk_result['data']
                stok_sekarang = produk.get('stok', 0)
                stok_baru = stok_sekarang + jumlah_dibeli
                update_result = db.update_one(config.MONGO_PRODUK_COLLECTION, {'kode_produk': produk_kode}, {'stok': stok_baru})
                if not update_result['status']:
                    return jsonify({'message': 'Terjadi kesalahan saat menambah stok'}), 500
            else:
                return jsonify({'message': f'Produk dengan kode {produk_kode} tidak ditemukan'}), 404

        result = db.insert_many(collection_name, data)
        if result['status']:
            return jsonify({'message': 'Detail pembelian berhasil ditambahkan'}), 201
        else:
            return jsonify({'message': result['message']}), 500

    except (ValueError, KeyError) as e:
        return jsonify({'message': f'Kesalahan input data: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Terjadi kesalahan: {str(e)}'}), 500


@app.route('/update_detail_pembelian/<pembelian_id>', methods=['PUT'])
def update_detail_pembelian(pembelian_id):
    data = request.get_json()
    result = db.update_one(config.MONGO_DETAIL_PEMBELIAN_COLLECTION, {'_id': pembelian_id}, data)
    if result['status']:
        return jsonify({'message': 'Detail pembelian berhasil diperbarui'})
    else:
        return jsonify({'message': result['message']}), 404

@app.route('/hapus_detail_pembelian/<pembelian_id>', methods=['DELETE'])
def hapus_detail_pembelian(pembelian_id):
    result = db.delete_one(config.MONGO_DETAIL_PEMBELIAN_COLLECTION, {'_id': pembelian_id})
    if result['status']:
        return jsonify({'message': 'Detail pembelian berhasil dihapus'})
    else:
        return jsonify({'message': result['message']}), 404
    
@app.route('/penjualan', methods=['GET'])
def penjualan():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    search_field = 'tanggal'

    result = db.find_all(config.MONGO_PENJUALAN_COLLECTION, page=page, per_page=per_page, search_query=search_query, search_field=search_field)
    
    if result['status']:
        penjualan_data = result['data']
        total_penjualan = result['total_documents']
    else:
        penjualan_data = []
        total_penjualan = 0

    products_result = db.find_all(config.MONGO_PRODUK_COLLECTION, page=1, per_page=0)
    if products_result['status']:
        products = products_result['data']
    else:
        products = []

    membership_result = db.find_all(config.MONGO_MEMBERSHIP_COLLECTION, page=1, per_page=0)
    if membership_result['status']:
        membership = membership_result['data']
    else:
        membership = []

    return render_template('penjualan.html', 
                           penjualan_data=penjualan_data, 
                           page=page, 
                           per_page=per_page, 
                           total_penjualan=total_penjualan, 
                           search=search_query,
                           products=products,
                           membership = membership
                           )

@app.route('/penjualan/tambah', methods=['POST'])
def tambah_penjualan():
    data = request.json
    if not data:
        return jsonify({'message': 'Tidak ada data yang dikirim'}), 400

    try:
        total = data['total']
        member = data['member']
        diskon_member = data['diskon_member']
        bayar = data['bayar']
        diterima = data['diterima']
        products = data['products']
        waktu_sekarang = datetime.now()

        penjualan = {
            'tanggal': waktu_sekarang,
            'total': total,
            'member': member,
            'diskon_member': diskon_member,
            'bayar': bayar,
            'diterima': diterima,
            'products': products
        }

        for product in products:
            kode_produk = product['kode_produk']
            jumlah_terjual = int(product['jumlah'])
            produk_result = db.find_one(config.MONGO_PRODUK_COLLECTION, {'kode_produk': kode_produk})
            if produk_result['status']:
                produk = produk_result['data']
                stok_sekarang = produk['stok']
                if stok_sekarang >= jumlah_terjual:
                    stok_baru = stok_sekarang - jumlah_terjual
                    update_result = db.update_one(config.MONGO_PRODUK_COLLECTION, {'kode_produk': kode_produk}, {'stok': stok_baru})
                    if not update_result['status']:
                        return jsonify({'message': 'Terjadi kesalahan saat mengurangi stok'}), 500
                else:
                    return jsonify({'message': 'Stok produk tidak mencukupi'}), 400
            else:
                return jsonify({'message': 'Produk tidak ditemukan'}), 404

        result = db.insert_one(config.MONGO_PENJUALAN_COLLECTION, penjualan)
        if result['status']:
            return jsonify({'message': 'Penjualan berhasil ditambahkan.'}), 200
        else:
            return jsonify({'message': 'Terjadi kesalahan saat menambahkan penjualan.'}), 500

    except (ValueError, KeyError) as e:
        return jsonify({'message': f'Kesalahan input data: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'message': f'Terjadi kesalahan: {str(e)}'}), 500

#Laporan Penjualan
@app.route('/laporan_penjualan', methods=['GET'])
def laporan_penjualan():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    per_page = 10
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    search_field = 'member'

    result = db.find_all(config.MONGO_PENJUALAN_COLLECTION, page=page, per_page=per_page, search_query=search_query, search_field=search_field)
    
    if result['status']:
        laporan_penjualan_data = result['data']
        total_laporan_penjualan = result['total_documents']
    else:
        laporan_penjualan_data = []
        total_laporan_penjualan = 0

    return render_template('laporan_penjualan.html', 
                           laporan_penjualan_data=laporan_penjualan_data, 
                           page=page, 
                           per_page=per_page, 
                           total_laporan_penjualan=total_laporan_penjualan, 
                           search=search_query,
                        )

@app.route('/penjualan/delete/<penjualan_id>', methods=['DELETE'])
def hapus_penjualan(penjualan_id):
    result = db.delete_one(config.MONGO_PENJUALAN_COLLECTION, {'_id': ObjectId(penjualan_id)})
    if result['status']:
        return jsonify({'message': 'Laporan penjualan berhasil dihapus.'}), 200
    else:
        return jsonify({'message': 'Terjadi kesalahan saat menghapus laporan penjualan.'})

if __name__ == '__main__':
    app.run(debug=True)
