from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Gudang(Base):
    __tablename__ = "gudang"
    id = Column(Integer, primary_key=True)
    nama_gudang = Column(String, nullable=False) # <--- Gunakan nama_gudang di sini
    raks = relationship("Rak", back_populates="gudang")

class Rak(Base):
    __tablename__ = "rak"
    id = Column(Integer, primary_key=True)
    nama_rak = Column(String)
    kode_rak = Column(String) # Tambah Kode
    gudang_id = Column(Integer, ForeignKey("gudang.id"))
    
    gudang = relationship("Gudang", back_populates="raks")
    toples_list = relationship("Toples", back_populates="rak", cascade="all, delete-orphan")

class Toples(Base):
    __tablename__ = "toples"
    id = Column(Integer, primary_key=True)
    nama_toples = Column(String)
    rak_id = Column(Integer, ForeignKey("rak.id"))
    
    rak = relationship("Rak", back_populates="toples_list")
    # Sekarang toples punya banyak barang
    barangs = relationship("Barang", back_populates="toples", cascade="all, delete-orphan")

class Barang(Base):
    __tablename__ = "barang"
    id = Column(Integer, primary_key=True)
    nama_barang = Column(String, nullable=False)
    kode_barang = Column(String, unique=True) # Ini untuk SKU kamu
    foto_barang = Column(String) 
    
    # Kolom Status Baru (Tersedia, Hampir Habis, Kosong)
    status = Column(String, default="Tersedia") 
    
    # Kolom jumlah tetap saya biarkan jika suatu saat kamu ingin mencatat angka kasar, 
    # tapi fokus utama pencarian kita nanti di 'status'.
    jumlah = Column(Integer, default=0) 
    
    toples_id = Column(Integer, ForeignKey("toples.id"))
    toples = relationship("Toples", back_populates="barangs")

class Aktifitas(Base):
    __tablename__ = "aktifitas"
    id = Column(Integer, primary_key=True)
    acara = Column(String)
    waktu = Column(DateTime, default=datetime.now)