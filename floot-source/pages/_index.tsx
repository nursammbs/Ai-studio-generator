import React from "react";
import { Link } from "react-router-dom";
import styles from "./_index.module.css";

const money = (n: number) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(n);
const products = [
  { key: "starter", name: "Starter", price: 29000, tag: "Mulai dari sini", features: ["Copy landing page satu halaman", "7 caption media sosial", "Pesan WhatsApp siap edit"] },
  { key: "growth", name: "Growth", price: 59000, tag: "Paling lengkap untuk promosi", features: ["Semua isi Starter", "3 ide kampanye promosi", "Sudut pesan yang lebih bervariasi"] },
  { key: "studio", name: "Studio", price: 99000, tag: "Rencana konten", features: ["Semua isi Growth", "Kalender konten 14 hari", "FAQ pelanggan siap edit"] },
];

export default function HomePage() {
  return <main className={styles.page}>
    <header className={styles.topbar}>
      <Link to="/" className={styles.brand}><span className={styles.mark}>cc</span><span><b>CepatCuan</b><small>STUDIO / UMKM GROWTH KIT</small></span></Link>
      <nav><a href="#cara-kerja">Cara kerja</a><a href="#harga">Paket</a><Link to="/studio">Studio saya ↗</Link></nav>
    </header>
    <section className={styles.hero}>
      <div className={styles.heroCopy}>
        <div className={styles.eyebrow}><span className={styles.liveDot}/> KIT PROMOSI DIGITAL · BAHASA INDONESIA</div>
        <h1>Promosi usaha kecil.<br/><em>Lebih cepat siap.</em></h1>
        <p className={styles.lead}>Ubah brief bisnis menjadi copy landing page, caption sosial media, pesan WhatsApp, dan ide promosi yang bisa langsung kamu edit. Dibuat untuk pemilik usaha lokal yang ingin bergerak, bukan mulai dari halaman kosong.</p>
        <div className={styles.heroActions}><Link to="/pesan-kit" className={styles.primary}>Buat kit untuk bisnis saya <span>↗</span></Link><a className={styles.secondary} href="#contoh">Lihat contoh hasil ↓</a></div>
        <div className={styles.proofLine}><span>✓</span> Sekali bayar · Hasil bisa disalin dan diunduh · Tanpa langganan wajib</div>
      </div>
      <div className={styles.previewCard}>
        <div className={styles.windowBar}><span/><span/><span/><small>CONTOH KIT / LAUNDRY FIKTIF</small></div>
        <div className={styles.mockupBody}>
          <div className={styles.tag}>LANDING PAGE COPY</div>
          <h2>Laundry Kilat</h2>
          <p className={styles.mockHeadline}>Pakaian bersih, urusan lebih praktis.</p>
          <p className={styles.mockSub}>Contoh konsep untuk usaha laundry di Makassar. Detail layanan, harga, dan ketersediaan wajib dikonfirmasi oleh pemilik bisnis.</p>
          <div className={styles.mockButton}>Tanya layanan via WhatsApp <span>↗</span></div>
          <div className={styles.mockDivider}/>
          <div className={styles.caption}><span>CAPTION 01</span><p>Butuh laundry yang cocok dengan rutinitasmu? Tanya pilihan layanan dan jadwal yang tersedia lewat WhatsApp.</p></div>
          <div className={styles.mockFooter}><span>7 CAPTION</span><span>3 IDE PROMO</span><span>CTA WHATSAPP</span></div>
        </div>
      </div>
    </section>
    <section className={styles.benefits} id="cara-kerja">
      <div className={styles.sectionIntro}><div className={styles.eyebrow}>ALUR SEDERHANA</div><h2>Dari brief ke bahan promosi.</h2><p>Kamu memberi konteks bisnis yang benar. Generator merangkai draf yang relevan. Kamu tetap memeriksa fakta sebelum mempublikasikan.</p></div>
      <div className={styles.steps}><article><span>01</span><h3>Ceritakan bisnisnya</h3><p>Nama, jenis usaha, kota, layanan, dan tujuan promosi.</p></article><article><span>02</span><h3>Bayar sekali</h3><p>Checkout melalui Midtrans. Metode yang tersedia mengikuti akun merchant.</p></article><article><span>03</span><h3>Ambil hasilnya</h3><p>Kit dibuat otomatis setelah pembayaran terkonfirmasi, lalu bisa disalin atau diunduh.</p></article></div>
    </section>
    <section className={styles.exampleSection} id="contoh"><div className={styles.exampleCopy}><div className={styles.eyebrow}>CONTOH OUTPUT</div><h2>Bukan template kosong.</h2><p>Hasil mengikuti brief yang kamu masukkan. Detail yang tidak kamu berikan tidak boleh dianggap fakta—periksa promosi, harga, jam buka, dan janji layanan sebelum dipakai.</p><Link to="/pesan-kit" className={styles.textLink}>Coba dengan brief bisnis sendiri →</Link></div><div className={styles.exampleList}><div><span>01 / HEADLINE</span><b>Jasa lokal yang membantu hari Anda berjalan lebih praktis.</b></div><div><span>02 / PESAN WHATSAPP</span><p>Halo, saya ingin tahu pilihan layanan, harga terbaru, dan jadwal yang tersedia. Bisa dibantu informasinya?</p></div><div><span>03 / ARAH KONTEN</span><p>Kenalkan layanan · Jawab pertanyaan pelanggan · Jelaskan cara pemesanan</p></div></div></section>
    <section className={styles.pricing} id="harga"><div className={styles.pricingHead}><div><div className={styles.eyebrow}>PAKET SEKALI BAYAR</div><h2>Pilih kit yang dibutuhkan.</h2></div><p>Harga peluncuran untuk diuji dan dapat berubah. Tidak ada janji peningkatan penjualan atau hasil viral.</p></div>
      <div className={styles.priceGrid}>{products.map((p, i) => <article key={p.key} className={`${styles.priceCard} ${i === 1 ? styles.featured : ""}`}><div className={styles.priceTag}>{p.tag}</div><h3>{p.name}</h3><div className={styles.price}>{money(p.price)}<small> / sekali</small></div><p className={styles.noSub}>Tanpa langganan berulang.</p><ul>{p.features.map(f => <li key={f}><span>✓</span>{f}</li>)}</ul><Link to={`/pesan-kit?paket=${p.key}`} className={i === 1 ? styles.primary : styles.cardButton}>Pilih {p.name} <span>→</span></Link></article>)}</div>
      <p className={styles.priceNote}>Pembayaran sungguhan aktif setelah pemilik toko menyelesaikan verifikasi merchant dan konfigurasi rekening settlement di Midtrans. Data rekening tidak diminta di halaman pelanggan.</p>
    </section>
    <footer className={styles.footer}><Link to="/" className={styles.brand}><span className={styles.mark}>cc</span><span><b>CepatCuan</b><small>STUDIO</small></span></Link><span>Alat bantu pembuatan draf. Periksa fakta sebelum publikasi. <Link to="/ketentuan">Ketentuan</Link> · <Link to="/privasi">Privasi</Link></span><Link to="/studio">Akses studio →</Link></footer>
  </main>;
}