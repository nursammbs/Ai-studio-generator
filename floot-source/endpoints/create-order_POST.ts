import { createHash, randomBytes } from "node:crypto";
import superjson from "superjson";
import { db } from "../helpers/db";
import { schema, type OutputType } from "./create-order_POST.schema";

const products = {
  starter: { name: "Starter — Kit Konten UMKM", amount: 29000, category: "digital-content" },
  growth: { name: "Growth — Kit Promo + Landing Copy", amount: 59000, category: "digital-content" },
  studio: { name: "Studio — Kit + Kalender 14 Hari", amount: 99000, category: "digital-content" },
} as const;

const sha256 = (value: string) => createHash("sha256").update(value).digest("hex");

export async function handle(request: Request) {
  try {
    const input = schema.parse(superjson.parse(await request.text()));
    if (input.website?.trim()) return new Response(superjson.stringify({ error: "Permintaan tidak valid." }), { status: 400 });

    const env = process.env as unknown as Record<string, string | undefined>;
    const serverKey = env["MIDTRANS_SERVER_KEY"];
    const environment = env["MIDTRANS_ENV"]?.toLowerCase();
    if (!serverKey || !environment || !["sandbox", "production"].includes(environment)) {
      return new Response(superjson.stringify({ error: "Checkout sedang disiapkan. Pemilik toko perlu menghubungkan akun Midtrans dan mengatur rekening settlement terlebih dahulu." }), { status: 503 });
    }

    const product = products[input.productKey];
    const orderId = `CC-${Date.now()}-${randomBytes(6).toString("hex")}`;
    const accessToken = randomBytes(24).toString("hex");
    const requestUrl = new URL(request.url);
    // Checkout returns to the published customer-facing site even when the owner tests from the sandbox preview.
    const requestOrigin = requestUrl.hostname.endsWith(".sandbox.floot.app") ? "https://cepatcuan-studio.floot.app" : requestUrl.origin;
    const finishUrl = `${requestOrigin}/pesanan?order=${encodeURIComponent(orderId)}&token=${encodeURIComponent(accessToken)}`;

    await db.insertInto("orders").values({
      orderId,
      tokenHash: sha256(accessToken),
      customerName: input.customerName,
      customerEmail: input.customerEmail.toLowerCase(),
      businessName: input.businessName,
      niche: input.niche,
      city: input.city,
      offer: input.offer,
      brief: input.brief,
      productKey: input.productKey,
      productName: product.name,
      amount: product.amount,
      currency: "IDR",
      status: "pending",
    }).executeTakeFirstOrThrow();

    const snapEndpoint = environment === "production" ? "https://app.midtrans.com/snap/v1/transactions" : "https://app.sandbox.midtrans.com/snap/v1/transactions";
    const auth = Buffer.from(`${serverKey}:`, "utf8").toString("base64");
    const midtransResponse = await fetch(snapEndpoint, {
      method: "POST",
      headers: { "Accept": "application/json", "Content-Type": "application/json", "Authorization": `Basic ${auth}`, "X-Override-Notification": `${requestOrigin}/_api/midtrans-notification` },
      body: JSON.stringify({
        transaction_details: { order_id: orderId, gross_amount: product.amount },
        item_details: [{ id: input.productKey, price: product.amount, quantity: 1, name: product.name.slice(0, 50), category: product.category }],
        customer_details: { first_name: input.customerName, email: input.customerEmail.toLowerCase() },
        callbacks: { finish: finishUrl },
        expiry: { unit: "minutes", duration: 60 },
      }),
    });

    if (!midtransResponse.ok) {
      await db.updateTable("orders").set({ status: "failed", updatedAt: new Date() }).where("orderId", "=", orderId).execute();
      return new Response(superjson.stringify({ error: "Midtrans belum menerima transaksi ini. Periksa konfigurasi akun merchant, lalu coba lagi." }), { status: 502 });
    }
    const payment = await midtransResponse.json() as { redirect_url?: string };
    if (!payment.redirect_url || !payment.redirect_url.startsWith("https://")) {
      await db.updateTable("orders").set({ status: "failed", updatedAt: new Date() }).where("orderId", "=", orderId).execute();
      return new Response(superjson.stringify({ error: "Tautan checkout aman tidak diterima dari penyedia pembayaran." }), { status: 502 });
    }
    return new Response(superjson.stringify({ orderId, accessToken, paymentUrl: payment.redirect_url, amount: product.amount, productName: product.name } satisfies OutputType), { headers: { "Content-Type": "application/json" } });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Terjadi kesalahan.";
    const isValidation = message.includes("Invalid input") || message.includes("Zod");
    return new Response(superjson.stringify({ error: isValidation ? "Periksa kembali nama, email, dan brief bisnis." : "Pesanan belum dapat dibuat. Coba lagi beberapa saat lagi." }), { status: isValidation ? 400 : 500, headers: { "Content-Type": "application/json" } });
  }
}