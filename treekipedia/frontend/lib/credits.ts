import { fetchJsonWithAuth } from './auth-api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://treekipedia-api.silvi.earth';

export interface CreditBalance {
  balance: number;
  lifetime_purchased: number;
  lifetime_spent: number;
}

export interface CreditPack {
  id: string;
  name: string;
  credits: number;
  price_usd: string;
}

export interface CreditTransaction {
  id: number;
  amount: number;
  type: string;
  reference_id: string | null;
  description: string;
  balance_after: number;
  metadata: Record<string, any>;
  created_at: string;
}

export interface AnalysisCostEstimate {
  success: boolean;
  area_hectares: number;
  cost_credits: number;
}

export async function getCreditBalance(): Promise<CreditBalance> {
  return fetchJsonWithAuth<CreditBalance>('/api/credits/balance');
}

export async function getCreditPacks(): Promise<CreditPack[]> {
  const res = await fetch(`${API_BASE_URL}/api/credits/packs`);
  if (!res.ok) throw new Error('Failed to fetch credit packs');
  const data = await res.json();
  return data.packs;
}

export async function createCreditInvoice(packId: string): Promise<{ invoice_url: string }> {
  return fetchJsonWithAuth<{ invoice_url: string }>('/api/payments/create-invoice', {
    method: 'POST',
    body: JSON.stringify({ pack_id: packId }),
  });
}

export async function estimateAnalysisCost(geometry: { type: 'Polygon'; coordinates: number[][][] }): Promise<AnalysisCostEstimate> {
  const res = await fetch(`${API_BASE_URL}/api/credits/estimate-analysis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ geometry }),
  });
  if (!res.ok) throw new Error('Failed to estimate analysis cost');
  return res.json();
}

export async function getCreditTransactions(limit = 50, offset = 0): Promise<{
  transactions: CreditTransaction[];
  total: number;
}> {
  return fetchJsonWithAuth<{ transactions: CreditTransaction[]; total: number }>(
    `/api/credits/transactions?limit=${limit}&offset=${offset}`
  );
}
