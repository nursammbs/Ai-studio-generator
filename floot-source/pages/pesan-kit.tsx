import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { postCreateOrder } from "../endpoints/create-order_POST.schema";
import styles from "./pesan-kit.module.css";

const products = [
  { key: "starter" as const, name: "Starter", price: 29000, note: "Landing page copy + 7 caption + pesan WhatsApp" },
  { key: "growth" as const, name: "Growth", price: 59000, note: "Semua Starter + 3 ide kampanye promosi" },
  { key: "studio" as const, name: "Studio", price: 99000, note: "Semua Growth + kalender konten 14 hari + FAQ" },
];
const currency = (n: number) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(n);

export default function PesanKitPage() {
  const [search] = useSearchParams();
  const initialProduct = products.some(p => p.key === search.get("paket")) ? search.get("paket")! : "growth";
  const [productKey, setProductKey] = useState(initialProduct);
  const [form, setForm] = useState({ customerName: "", customerEmail: "", businessName: "", niche: "Laundry", city: "Makassar", offer: "", brief: "", website: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedProduct = products.find(p => p.key === productKey)!;
  const update = (key: keyof typeof form, value: string) => setForm(old => ({ ...old, [key]: value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const result = await postCreateOrder({ ...form, productKey } as Parameters<typeof postCreateOrder>[0]);
      // The server creates a fixed-price order and Midtrans-hosted checkout; no payment secrets enter the browser.
      window.location.assign(result.paymentUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout belum dapat dibuka. Coba lagi.");
      setBusy(false);
    }
  };

  return <main className={styles.page}>
    <header className={styles.header}><Link to="/" className={styles.brand}><span>cc</span><b>CepatCuan <small>STUDIO</small></b></Link><Link to="/" className={styles.back}>← Kembali ke beranda</Link></header>
    <div className={styles.wrap}>
      <section className={styles.intro}><div className={styles.eyebrow}>CHECKOUT / KIT DIGITAL UMKM</div><h1>Siapkan kit promosi<br/><em>untuk bisnismu.</em></h1><p>Lengkapi brief yang benar. Setelah pembayaran terkonfirmasi, sistem menyusun kit dan menampilkan tautan hasil privat yang bisa kamu salin atau unduh.</p><div className={styles.badges}><span>01 · Sekali bayar</span><span>02 · Diproses otomatis</span><span>03 · Bisa diunduh</span></div></section>
      <form className={styles.form} onSubmit={submit}>
        <section className={styles.formSection}><div className={styles.sectionTop}><span>01</span><div><h2>Pilih paket</h2><p>Harga peluncuran untuk validasi pasar.</p></div></div><div className={styles.options}>{products.map(p => <button type="button" key={p.key} className={`${styles.option} ${productKey === p.key ? styles.selected : ""}`} onClick={() => setProductKey(p.key)}><span className={styles.radio}>{productKey === p.key ? "✓" : ""}</span><span className={styles.optionText}><b>{p.name}</b><small>{p.note}</small></span><strong>{currency(p.price)}</strong></button>)}</div></section>
        <section className={styles.formSection}><div className={styles.sectionTop}><span>02</span><div><h2>Kontak pemesan</h2><p>Email dipakai untuk identifikasi pesanan. Jangan masukkan kata sandi atau data kartu.</p></div></div><div className={styles.fields}><label>Nama kamu<input autoComplete="name" required minLength={2} maxLength={100} value={form.customerName} onChange={e => update("customerName", e.target.value)} placeholder="Nama pemesan"/></label><label>Email aktif<input autoComplete="email" required type="email" maxLength={254} value={form.customerEmail} onChange={e => update("customerEmail", e.target.value)} placeholder="nama@email.com"/></label></div></section>
        <section className={styles.formSection}><div className={styles.sectionTop}><span>03</span><div><h2>Brief bisnis</h2><p>Semakin nyata detailnya, semakin relevan draf yang dihasilkan.</p></div></div><div className={styles.fields}><label>Nama bisnis<input required minLength={2} maxLength={120} value={form.businessName} onChange={e => update("businessName", e.target.value)} placeholder="Contoh: Laundry Bersih Jaya"/></label><label>Jenis usaha<select value={form.niche} onChange={e => update("niche", e.target.value)}>{["Laundry", "Makanan", "Barbershop", "Salon", "Agen properti", "Jasa lokal", "Lainnya"].map(n => <option key={n}>{n}</option>)}</select></label><label>Kota / area<input required minLength={2} maxLength={80} value={form.city} onChange={e => update("city", e.target.value)} placeholder="Contoh: Makassar"/></label><label>Layanan utama<input required minLength={2} maxLength={300} value={form.offer} onChange={e => update("offer", e.target.value)} placeholder="Contoh: cuci kiloan dan antar-jemput"/></label><label className={styles.full}>Detail yang boleh disebutkan<textarea required minLength={10} maxLength={1500} rows={5} value={form.brief} onChange={e => update("brief", e.target.value)} placeholder="Target pelanggan, keunggulan nyata, area layanan, cara memesan, gaya bahasa…"/><small>Hindari data pribadi pelanggan. Jangan tulis klaim, harga, diskon, atau jam buka yang belum benar.</small></label></div>
          <label className={styles.honeypot} aria-hidden="true">Website<input tabIndex={-1} autoComplete="off" value={form.website} onChange={e => update("website", e.target.value)}/></label>
        </section>
        <aside className={styles.summary}><div><span>PAKET DIPILIH</span><b>{selectedProduct.name}</b><small>{selectedProduct.note}</small></div><strong>{currency(selectedProduct.price)}</strong></aside>
        {error && <div className={styles.error} role="alert">{error}</div>}
        <button className={styles.payButton} type="submit" disabled={busy}>{busy ? "Menyiapkan checkout…" : <>Lanjutkan ke pembayaran aman <span>↗</span></>}</button>
        <p className={styles.legal}>Pembayaran diproses oleh Midtrans jika merchant sudah aktif. Metode pembayaran mengikuti akun merchant. Hasil adalah draf untuk diperiksa; generator tidak menjamin penjualan, viralitas, atau kebenaran fakta yang tidak kamu berikan.</p>
      </form>
    </div>
    <footer className={styles.footer}>CEPATCUAN STUDIO · PRIVASI DAN KEAMANAN DIUTAMAKAN <Link to="/studio">Studio pemilik →</Link></footer>
  </main>;
}