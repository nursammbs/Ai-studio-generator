import React from "react";
import { Link } from "react-router-dom";
import styles from "./info.module.css";

export default function PrivasiPage() {
  return <main className={styles.page}>
    <header className={styles.header}><Link to="/" className={styles.brand}><span>cc</span><b>CepatCuan <small>STUDIO</small></b></Link><Link to="/" className={styles.back}>← Beranda</Link></header>
    <article className={styles.article}><div className={styles.eyebrow}>DATA DAN PRIVASI</div><h1>Kebijakan privasi</h1><p className={styles.updated}>Terakhir diperbarui: 26 Oktober 2026</p>
      <h2>1. Data yang diproses</h2><p>Untuk membuat dan mengirim pesanan, layanan memproses nama pembeli, email, nama bisnis, jenis usaha, kota/area, layanan utama, brief, paket yang dipilih, nilai dan status order, serta referensi transaksi dari penyedia pembayaran. Jangan memasukkan data pribadi pelanggan bisnis, kredensial, data kartu, PIN, atau kata sandi ke dalam brief.</p>
      <h2>2. Tujuan penggunaan</h2><p>Data digunakan untuk membuat pesanan, meminta pembayaran, memverifikasi status pembayaran, menghasilkan kit yang dibeli, menjaga keamanan tautan pesanan, menangani kegagalan pengiriman, serta mencegah penyalahgunaan.</p>
      <h2>3. Pembayaran</h2><p>Informasi metode pembayaran ditangani pada checkout penyedia pembayaran. CepatCuan Studio tidak meminta atau menyimpan PIN, OTP, atau nomor kartu lengkap pada formulir brief. Nomor rekening pemilik usaha dikonfigurasi pada dashboard merchant penyedia pembayaran, bukan di situs ini.</p>
      <h2>4. AI dan pihak pemroses</h2><p>Brief bisnis dapat dikirim ke layanan AI yang dikonfigurasi untuk menghasilkan draf promosi. Jangan memasukkan rahasia dagang yang tidak ingin diproses pihak penyedia AI. Status transaksi diproses oleh penyedia pembayaran. Data hanya digunakan untuk fungsi layanan dan keamanan, bukan untuk membuat testimoni atau klaim pemasaran palsu.</p>
      <h2>5. Tautan hasil privat</h2><p>Halaman pesanan memakai token acak sebagai akses. Siapa pun yang memiliki tautan dapat melihat hasil pesanan tersebut. Simpan dengan aman dan hindari menempelkannya di kanal publik.</p>
      <h2>6. Penyimpanan dan keamanan</h2><p>Data order disimpan di database aplikasi dan dibatasi berdasarkan kebutuhan layanan. Kredensial merchant disimpan sebagai konfigurasi server-side; kredensial tidak boleh dikirim melalui formulir publik atau chat. Tidak ada sistem yang dapat menjamin keamanan absolut, tetapi kontrol akses dan verifikasi webhook digunakan untuk mengurangi risiko.</p>
      <h2>7. Retensi dan permintaan data</h2><p>Data pesanan disimpan selama diperlukan untuk pemenuhan produk, pencatatan transaksi, keamanan, dan kewajiban hukum yang berlaku. Untuk pertanyaan akses atau penghapusan data, gunakan kanal dukungan merchant yang tercantum pada bukti transaksi, dengan nomor order sebagai referensi.</p>
      <h2>8. Perubahan kebijakan</h2><p>Kebijakan dapat diperbarui ketika layanan atau persyaratan hukum berubah. Versi terbaru akan ditampilkan di halaman ini.</p>
      <Link to="/ketentuan" className={styles.textLink}>Baca ketentuan layanan →</Link>
    </article><footer className={styles.footer}>CEPATCUAN STUDIO · <Link to="/ketentuan">Ketentuan</Link></footer>
  </main>;
}
