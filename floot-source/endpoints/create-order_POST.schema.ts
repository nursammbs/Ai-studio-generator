import { z } from "zod";
import superjson from "superjson";

export const schema = z.object({
  customerName: z.string().trim().min(2).max(100),
  customerEmail: z.string().trim().email().max(254),
  businessName: z.string().trim().min(2).max(120),
  niche: z.enum(["Laundry", "Makanan", "Barbershop", "Salon", "Agen properti", "Jasa lokal", "Lainnya"]),
  city: z.string().trim().min(2).max(80),
  offer: z.string().trim().min(2).max(300),
  brief: z.string().trim().min(10).max(1500),
  productKey: z.enum(["starter", "growth", "studio"]),
  website: z.string().max(200).optional(),
});

export type InputType = z.infer<typeof schema>;
export type OutputType = { orderId: string; accessToken: string; paymentUrl: string; amount: number; productName: string };

export const postCreateOrder = async (body: InputType, init?: RequestInit): Promise<OutputType> => {
  const validatedInput = schema.parse(body);
  const response = await fetch("/_api/create-order", {
    method: "POST",
    body: superjson.stringify(validatedInput),
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let error = "Pesanan belum dapat dibuat. Coba lagi.";
    try { error = superjson.parse<{ error?: string }>(await response.text()).error ?? error; } catch { /* keep safe generic message */ }
    throw new Error(error);
  }
  return superjson.parse<OutputType>(await response.text());
};