import React from "react";
import { Link } from "react-router-dom";
import styles from "./info.module.css";

export default function KetentuanPage() {
  return <main className={styles.page}>
    <header className={styles.header}><Link to="/" className={styles.brand}><span>cc</span><b>CepatCuan <small>STUDIO</small></b></Link><Link to="/" className={styles.back}>← Beranda</Link></header>
    <article className={styles.article}><div className={styles.eyebrow}>INFORMASI LAYANAN</div><h1>Ketentuan layanan</h1><p className={styles.updated}>Terakhir diperbarui: 26 Oktober 2026</p>
      <h2>1. Produk digital</h2><p>CepatCuan Studio menyediakan draf materi promosi untuk bisnis kecil, termasuk teks landing page, caption, pesan WhatsApp, dan materi lain sesuai paket. Deliverable disiapkan berdasarkan brief yang dikirim pembeli.</p>
      <h2>2. Harga dan pembayaran</h2><p>Harga yang tampil di halaman paket adalah harga yang digunakan saat order dibuat. Pembayaran diproses melalui halaman checkout penyedia pembayaran. Jangan mengirim nomor kartu, PIN, kata sandi, atau kode OTP melalui chat. Pesanan hanya ditandai lunas setelah notifikasi pembayaran terverifikasi oleh server.</p>
      <h2>3. Penggunaan AI dan pemeriksaan fakta</h2><p>Materi dapat dihasilkan dengan bantuan AI atau generator cadangan. Hasil merupakan draf, bukan nasihat hukum, keuangan, atau jaminan kinerja pemasaran. Pembeli harus memeriksa fakta, hak cipta, harga, promo, jam buka, ketersediaan, dan klaim sebelum memublikasikan. Jangan memasukkan data pribadi atau rahasia pelanggan ke brief.</p>
      <h2>4. Pengiriman</h2><p>Setelah pembayaran dikonfirmasi, sistem akan menyiapkan kit dan menampilkan hasil pada halaman pesanan dengan tautan privat. Simpan tautan tersebut. Jangan membagikannya karena tautan memungkinkan siapa pun yang memegangnya melihat hasil dari pesanan yang sama.</p>
      <h2>5. Pembatalan, kendala dan pengembalian dana</h2><p>Jika terjadi pembayaran ganda, pembayaran terkonfirmasi tetapi kit tidak dapat diakses, atau jumlah tagihan tidak sesuai, simpan nomor pesanan dan hubungi dukungan merchant melalui kontak pada halaman pembayaran atau bukti transaksi. Permintaan ditinjau berdasarkan status pembayaran, bukti transaksi, serta apakah produk digital sudah terkirim. Hak konsumen yang berlaku tetap dihormati; tidak ada ketentuan di halaman ini yang menghapus hak wajib menurut hukum.</p>
      <h2>6. Tidak ada jaminan pendapatan</h2><p>Penggunaan kit tidak menjamin pelanggan baru, omzet, ranking mesin pencari, atau konten viral. Hasil bergantung pada banyak faktor di luar kendali layanan ini.</p>
      <h2>7. Penyalahgunaan</h2><p>Pengguna tidak boleh menggunakan layanan untuk penipuan, spam, menyamar sebagai orang lain, menyebarkan informasi palsu, atau melanggar hak pihak ketiga.</p>
      <div className={styles.callout}>Sebelum menerima transaksi live, pemilik toko wajib melengkapi pengaturan merchant, kontak dukungan, dan rekening settlement pada penyedia pembayaran.</div>
      <Link to="/privasi" className={styles.textLink}>Baca kebijakan privasi →</Link>
    </article><footer className={styles.footer}>CEPATCUAN STUDIO · <Link to="/privasi">Privasi</Link></footer>
  </main>;
}
