import { createHash, timingSafeEqual } from "node:crypto";
import { db } from "../helpers/db";
import { generateKit } from "../helpers/generateKit";
import { schema } from "./order-status_GET.schema";

const sha256 = (value: string) => createHash("sha256").update(value).digest("hex");

function allowedDeliverable(full: any, productKey: string) {
  if (!full || typeof full !== "object") return null;
  const base = {
    headline: full.headline,
    subheadline: full.subheadline,
    landingSections: full.landingSections,
    cta: full.cta,
    whatsappMessage: full.whatsappMessage,
    captions: full.captions,
  };
  if (productKey === "growth" || productKey === "studio") return { ...base, promoIdeas: full.promoIdeas, ...(productKey === "studio" ? { calendar14: full.calendar14, faqs: full.faqs } : {}) };
  return base;
}

export async function handle(request: Request) {
  const url = new URL(request.url);
  const parsed = schema.safeParse({ orderId: url.searchParams.get("order"), token: url.searchParams.get("token") });
  if (!parsed.success) return Response.json({ error: "Tautan pesanan tidak lengkap atau sudah rusak." }, { status: 400 });
  const { orderId, token } = parsed.data;
  const order = await db.selectFrom("orders").selectAll().where("orderId", "=", orderId).executeTakeFirst();
  if (!order) return Response.json({ error: "Pesanan tidak ditemukan." }, { status: 404 });
  const received = Buffer.from(sha256(token), "hex");
  const stored = Buffer.from(order.tokenHash, "hex");
  if (received.length !== stored.length || !timingSafeEqual(received, stored)) return Response.json({ error: "Tautan pesanan tidak valid." }, { status: 404 });

  let current = order;
  if (current.status === "paid" && !current.deliverable) {
    try {
      const generated = await generateKit(current);
      await db.updateTable("orders").set({ deliverable: generated.content, aiGenerated: generated.aiGenerated, aiError: generated.aiError, updatedAt: new Date() }).where("orderId", "=", orderId).where("deliverable", "is", null).execute();
      current = await db.selectFrom("orders").selectAll().where("orderId", "=", orderId).executeTakeFirstOrThrow();
    } catch {
      return Response.json({ error: "Pembayaran terkonfirmasi. Kit sedang disiapkan; tekan Periksa Lagi sebentar lagi." }, { status: 503 });
    }
  }

  return Response.json({
    orderId: current.orderId,
    productName: current.productName,
    productKey: current.productKey,
    amount: current.amount,
    status: current.status,
    aiGenerated: current.aiGenerated,
    deliverable: current.status === "paid" ? allowedDeliverable(current.deliverable, current.productKey) : null,
    createdAt: new Date(current.createdAt).toISOString(),
  });
}