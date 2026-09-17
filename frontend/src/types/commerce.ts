export interface Product {
  id: string;
  title: string;
  brand: string;
  major_category: string;
  subcategory: string;
  product_type: string;
  price: string;
  original_price: string;
  currency: string;
  average_rating: string;
  rating_count: number;
  image_url: string;
  description: string;
  features: string[];
  attributes: Record<string, string | string[]>;
  source: string;
  inventory: {
    available: boolean;
    stock_quantity: number;
    shipping_days: number;
    discount_percentage: string;
  };
  score?: number;
  score_components?: Record<string, number>;
  reason?: string;
}
export interface CartItem {
  id: string;
  product: Product;
  quantity: number;
  variant: string;
  unit_price: string;
  line_total: string;
}
export interface Cart {
  id: string;
  items: CartItem[];
  subtotal: string;
  discounts: string;
  tax: string;
  total: string;
  currency: string;
}
export interface Checkout {
  id: string;
  snapshot: Cart;
  total: string;
  expires_at: string;
  confirmation_token: string;
  confirmed: boolean;
  message: string;
}
export interface Order {
  id: string;
  status: string;
  total: string;
  created_at: string;
  payment: string;
  items: {
    product_id: string;
    title: string;
    quantity: number;
    unit_price: string;
  }[];
}
export interface ChatResponse {
  session_id: string;
  message: string;
  intent: string;
  products?: Product[];
  comparison?: Product[];
  cart?: Cart;
  checkout?: Checkout;
  order?: Order;
  retrieval_mode?: string;
  warning?: string;
}
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}
