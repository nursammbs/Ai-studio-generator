import { createHash, timingSafeEqual } from "node:crypto";
import { db } from "../helpers/db";
import { generateKit } from "../helpers/generateKit";
import { schema } from "./midtrans-notification_POST.schema";

// This endpoint is called by Midtrans, not by a logged-in browser.
// floot:external
export const flootPublic = true;

export async function handle(request: Request) {
  if (request.method !== "POST") return Response.json({ error: "Method not allowed" }, { status: 405 });
  const env = process.env as unknown as Record<string, string | undefined>;
  const serverKey = env["MIDTRANS_SERVER_KEY"];
  if (!serverKey) return Response.json({ error: "Payment notification is not configured" }, { status: 503 });

  let payload: unknown;
  try { payload = await request.json(); } catch { return Response.json({ error: "Invalid JSON" }, { status: 400 }); }
  const parsed = schema.safeParse(payload);
  if (!parsed.success) return Response.json({ error: "Invalid notification shape" }, { status: 400 });
  const body = parsed.data;

  const expected = createHash("sha512").update(`${body.order_id}${body.status_code}${body.gross_amount}${serverKey}`).digest("hex");
  const receivedBytes = Buffer.from(body.signature_key, "hex");
  const expectedBytes = Buffer.from(expected, "hex");
  if (receivedBytes.length !== expectedBytes.length || !timingSafeEqual(receivedBytes, expectedBytes)) {
    return Response.json({ error: "Invalid signature" }, { status: 403 });
  }

  const order = await db.selectFrom("orders").selectAll().where("orderId", "=", body.order_id).executeTakeFirst();
  // Unknown order IDs can be acknowledged; they must never grant a product or alter another order.
  if (!order) return Response.json({ received: true });
  if (Math.round(Number(body.gross_amount)) !== order.amount || (body.currency && body.currency !== "IDR")) {
    return Response.json({ error: "Amount or currency mismatch" }, { status: 403 });
  }

  const isPaid = body.transaction_status === "settlement" || (body.transaction_status === "capture" && body.fraud_status === "accept");
  if (isPaid && order.status !== "paid") {
    const changed = await db.updateTable("orders").set({
      status: "paid",
      midtransTransactionId: body.transaction_id ?? null,
      midtransPaymentType: body.payment_type ?? null,
      midtransStatus: body.transaction_status,
      paidAt: new Date(),
      updatedAt: new Date(),
    }).where("orderId", "=", body.order_id).where("status", "!=", "paid").returning("orderId").executeTakeFirst();

    if (changed) {
      try {
        const generated = await generateKit(order);
        await db.updateTable("orders").set({ deliverable: generated.content, aiGenerated: generated.aiGenerated, aiError: generated.aiError, updatedAt: new Date() }).where("orderId", "=", body.order_id).execute();
      } catch {
        // Payment remains recorded as paid. The private order page can retry generation without charging again.
      }
    }
  } else if (["expire", "deny", "cancel"].includes(body.transaction_status) && order.status !== "paid") {
    await db.updateTable("orders").set({ status: body.transaction_status === "expire" ? "expired" : "failed", midtransStatus: body.transaction_status, updatedAt: new Date() }).where("orderId", "=", body.order_id).where("status", "!=", "paid").execute();
  } else if (order.status === "paid" && !order.deliverable) {
    // Retry a previously interrupted fulfillment, without changing the paid state.
    try {
      const generated = await generateKit(order);
      await db.updateTable("orders").set({ deliverable: generated.content, aiGenerated: generated.aiGenerated, aiError: generated.aiError, updatedAt: new Date() }).where("orderId", "=", body.order_id).where("deliverable", "is", null).execute();
    } catch { /* acknowledge payment notification; the customer order page can retry */ }
  }

  return Response.json({ received: true });
}