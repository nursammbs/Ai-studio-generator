import React, { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getOrderStatus } from "../endpoints/order-status_GET.schema";
import styles from "./pesanan.module.css";

type Section = { heading: string; body: string };
type Deliverable = { headline?: string; subheadline?: string; landingSections?: Section[]; cta?: string; whatsappMessage?: string; captions?: string[]; promoIdeas?: string[]; calendar14?: { day: number; theme: string; caption: string }[]; faqs?: { question: string; answer: string }[] };
type OrderData = { orderId: string; productName: string; productKey: string; amount: number; status: string; aiGenerated: boolean; deliverable: Deliverable | null; createdAt: string };
const money = (n: number) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(n);

export default function PesananPage() {
  const [params] = useSearchParams();
  const orderId = params.get("order") ?? "";
  const token = params.get("token") ?? "";
  const [data, setData] = useState<OrderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    if (!orderId || !token) { setError("Tautan pesanan tidak lengkap. Buka kembali tautan dari checkout."); setLoading(false); return; }
    setLoading(true); setError("");
    try {
      const result = await getOrderStatus({ orderId, token });
      setData(result as OrderData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Koneksi bermasalah. Coba kembali.");
    } finally { setLoading(false); }
  };

  useEffect(() => { void load(); // one verified status request on arrival; refresh is manual to avoid unnecessary server polling
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId, token]);

  const kitText = useMemo(() => {
    const d = data?.deliverable;
    if (!d) return "";
    const sections = [d.headline, d.subheadline, "LANDING PAGE", ...(d.landingSections ?? []).flatMap(s => [s.heading, s.body]), d.cta ? `CTA: ${d.cta}` : "", "PESAN WHATSAPP", d.whatsappMessage ?? "", "7 CAPTION", ...(d.captions ?? []).map((c, i) => `${i + 1}. ${c}`), ...(d.promoIdeas ? ["IDE PROMOSI", ...d.promoIdeas.map((p, i) => `${i + 1}. ${p}`)] : []), ...(d.calendar14 ? ["KALENDER KONTEN 14 HARI", ...d.calendar14.map(x => `Hari ${x.day} — ${x.theme}\n${x.caption}`)] : []), ...(d.faqs ? ["FAQ", ...d.faqs.map(x => `${x.question}\n${x.answer}`)] : [])];
    return sections.filter(Boolean).join("\n\n");
  }, [data]);

  const copyKit = async () => {
    try { await navigator.clipboard.writeText(kitText); setNotice("Kit berhasil disalin. Periksa fakta sebelum dipublikasikan."); }
    catch { setNotice("Clipboard tidak tersedia di browser ini. Gunakan tombol Unduh TXT."); }
  };
  const downloadKit = () => {
    const blob = new Blob([kitText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `kit-${(data?.orderId ?? "cepatcuan").toLowerCase()}.txt`; a.click(); URL.revokeObjectURL(url);
  };

  return <main className={styles.page}>
    <header className={styles.header}><Link to="/" className={styles.brand}><span>cc</span><b>CepatCuan <small>STUDIO</small></b></Link><Link to="/" className={styles.back}>← Beranda</Link></header>
    <div className={styles.wrap}>
      <div className={styles.eyebrow}>ORDER DESK / STATUS PESANAN</div>
      <h1>{data?.status === "paid" ? "Kit kamu siap." : "Pesanan kamu."}</h1>
      <p className={styles.lead}>Status diambil dari notifikasi pembayaran yang diverifikasi di server. Halaman ini tidak menerima bukti transfer atau menganggap redirect sebagai bukti pembayaran.</p>
      {loading && <section className={styles.state}><span className={styles.spinner}/><h2>Memeriksa status pesanan…</h2><p>Ini bisa memerlukan beberapa saat setelah pembayaran.</p></section>}
      {!loading && error && <section className={styles.state}><span className={styles.stateIcon}>!</span><h2>Belum dapat ditampilkan</h2><p>{error}</p><button className={styles.primary} onClick={() => void load()}>Coba lagi</button></section>}
      {!loading && data && <>
        <section className={styles.orderCard}><div><span className={styles.label}>NOMOR PESANAN</span><b className={styles.orderId}>{data.orderId}</b></div><div><span className={styles.label}>PAKET</span><b>{data.productName}</b></div><div><span className={styles.label}>TOTAL</span><b className={styles.amount}>{money(data.amount)}</b></div><div><span className={styles.label}>STATUS</span><span className={`${styles.status} ${data.status === "paid" ? styles.paid : data.status === "pending" ? styles.pending : styles.failed}`}>{data.status === "paid" ? "PEMBAYARAN TERKONFIRMASI" : data.status === "pending" ? "MENUNGGU PEMBAYARAN" : data.status.toUpperCase()}</span></div></section>
        {data.status === "pending" && <section className={styles.state}><span className={styles.stateIcon}>◷</span><h2>Menunggu konfirmasi dari Midtrans</h2><p>Selesaikan pembayaran pada halaman Midtrans. Setelah penyedia pembayaran mengirim notifikasi terverifikasi, kit akan dibuat otomatis. Jika baru saja membayar, tekan Periksa Status lagi.</p><button className={styles.primary} onClick={() => void load()}>Periksa status lagi ↻</button></section>}
        {(data.status === "failed" || data.status === "expired") && <section className={styles.state}><span className={styles.stateIcon}>!</span><h2>Pembayaran belum berhasil</h2><p>Pesanan ini belum ditandai lunas. Jangan kirim ulang bukti transfer melalui formulir. Kamu dapat membuat pesanan baru dan mencoba metode pembayaran lain.</p><Link className={styles.primary} to="/pesan-kit">Buat pesanan baru →</Link></section>}
        {data.status === "paid" && data.deliverable && <>
          <div className={styles.ready}><span>✓</span><div><b>Kit berhasil dibuat</b><p>{data.aiGenerated ? "Draf dirangkai oleh AI berdasarkan brief kamu." : "Kit dibuat dengan generator cadangan karena layanan AI tidak tersedia pada saat pemrosesan."} Periksa semua fakta, harga, promo, dan klaim sebelum digunakan.</p></div></div>
          {notice && <div className={styles.notice}>{notice}</div>}
          <div className={styles.actions}><button className={styles.primary} onClick={() => void copyKit()}>Salin semua isi</button><button className={styles.secondary} onClick={downloadKit}>Unduh TXT ↓</button></div>
          <section className={styles.kit}><div className={styles.kitHeader}><span>01 / LANDING PAGE COPY</span><h2>{data.deliverable.headline}</h2><p>{data.deliverable.subheadline}</p></div>{data.deliverable.landingSections?.map((section, i) => <article key={i}><h3>{section.heading}</h3><p>{section.body}</p></article>)}<div className={styles.cta}>CTA YANG DISARANKAN <b>{data.deliverable.cta}</b></div></section>
          <section className={styles.kit}><div className={styles.kitHeader}><span>02 / WHATSAPP</span><h2>Pesan awal</h2></div><p className={styles.message}>{data.deliverable.whatsappMessage}</p><button className={styles.textBtn} onClick={async () => { try { await navigator.clipboard.writeText(data.deliverable?.whatsappMessage ?? ""); setNotice("Pesan WhatsApp disalin."); } catch { setNotice("Clipboard tidak tersedia; salin dari kotak teks ini."); } }}>Salin pesan →</button></section>
          <section className={styles.kit}><div className={styles.kitHeader}><span>03 / CAPTION</span><h2>7 caption siap diedit</h2></div><div className={styles.list}>{data.deliverable.captions?.map((caption, i) => <article key={i}><span>CAPTION {String(i + 1).padStart(2, "0")}</span><p>{caption}</p></article>)}</div></section>
          {data.deliverable.promoIdeas && <section className={styles.kit}><div className={styles.kitHeader}><span>04 / PROMO</span><h2>Ide kampanye</h2></div><ul className={styles.simpleList}>{data.deliverable.promoIdeas.map((idea, i) => <li key={i}>{idea}</li>)}</ul></section>}
          {data.deliverable.calendar14 && <section className={styles.kit}><div className={styles.kitHeader}><span>05 / KALENDER KONTEN</span><h2>14 hari ide posting</h2></div><div className={styles.calendar}>{data.deliverable.calendar14.map(item => <article key={item.day}><span>HARI {String(item.day).padStart(2, "0")}</span><b>{item.theme}</b><p>{item.caption}</p></article>)}</div></section>}
          {data.deliverable.faqs && <section className={styles.kit}><div className={styles.kitHeader}><span>06 / FAQ</span><h2>Jawaban untuk pelanggan</h2></div>{data.deliverable.faqs.map((item, i) => <article key={i}><h3>{item.question}</h3><p>{item.answer}</p></article>)}</section>}
        </>}
      </>}
      <div className={styles.support}>Butuh membuat kit lain? <Link to="/pesan-kit">Mulai pesanan baru →</Link> <span>·</span> <Link to="/">Lihat paket</Link></div>
    </div>
    <footer className={styles.footer}>CEPATCUAN STUDIO · Simpan tautan ini untuk membuka pesanan yang sama.</footer>
  </main>;
}