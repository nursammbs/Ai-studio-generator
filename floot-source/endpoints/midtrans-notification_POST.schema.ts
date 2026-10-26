import { z } from "zod";

export const schema = z.object({
  order_id: z.string().min(1).max(50),
  status_code: z.union([z.string(), z.number()]).transform(String),
  gross_amount: z.union([z.string(), z.number()]).transform(String),
  signature_key: z.string().regex(/^[a-f0-9]{128}$/i),
  transaction_status: z.string().min(1).max(40),
  transaction_id: z.string().max(120).optional(),
  payment_type: z.string().max(60).optional(),
  fraud_status: z.string().max(40).optional(),
  currency: z.string().max(8).optional(),
});

export type InputType = z.infer<typeof schema>;
export type OutputType = { received: boolean };