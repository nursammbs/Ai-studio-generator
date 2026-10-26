import { z } from "zod";
import superjson from "superjson";

export const schema = z.object({
  orderId: z.string().min(8).max(50),
  token: z.string().min(32).max(80),
});

export type InputType = z.infer<typeof schema>;
export type OutputType = {
  orderId: string;
  productName: string;
  productKey: string;
  amount: number;
  status: string;
  aiGenerated: boolean;
  deliverable: unknown | null;
  createdAt: string;
};

export const getOrderStatus = async (input: InputType, init?: RequestInit): Promise<OutputType> => {
  const validated = schema.parse(input);
  const query = new URLSearchParams({ order: validated.orderId, token: validated.token });
  const response = await fetch(`/_api/order-status?${query.toString()}`, {
    method: "GET",
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let message = "Status pesanan belum dapat diperiksa.";
    try { message = (await response.json()).error ?? message; } catch { /* safe generic message */ }
    throw new Error(message);
  }
  return (await response.json()) as OutputType;
};