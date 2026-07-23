"use client";
// Milestone 3 wires this to Daraja STK push. For launch it opens the order form.
export default function BuyButton({ product }: { product: any }) {
  return (
    <div className="buy-panel">
      <p>
        <strong>{product.small_pack_size}</strong> pack — KES {product.price_kes}
      </p>
      <a className="cta" href={`/quote?product=${product.slug}&mode=buy`}>
        Buy now (M-Pesa)
      </a>
    </div>
  );
}
