"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Star, Info, Eye, Loader2 } from "lucide-react";
import { getProductDetail, type DecideLine, type ProductDetail } from "@/lib/api";

const money = (n: number) => `₹${(Math.round(n * 100) / 100).toLocaleString("en-IN")}`;

function discountPct(price?: number, mrp?: number | null): number {
  if (!mrp || !price || mrp <= price) return 0;
  return Math.round((1 - price / mrp) * 100);
}

export function ProductModal({ line, onClose }: { line: DecideLine | null; onClose: () => void }) {
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeImg, setActiveImg] = useState(0);

  useEffect(() => {
    if (!line) return;
    setDetail(null);
    setActiveImg(0);
    setLoading(true);
    getProductDetail(line.offer_id)
      .then((d) => setDetail(d.found ? d : null))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [line]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (line) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [line, onClose]);

  if (!line) return null;

  const name = detail?.product_name ?? line.product_name;
  const brand = detail?.brand ?? line.brand ?? null;
  const price = detail?.unit_price ?? line.unit_price;
  const mrp = detail?.mrp ?? line.mrp ?? null;
  const rating = detail?.rating ?? line.rating ?? 0;
  const reviews = detail?.review_count ?? line.review_count ?? 0;
  const images = detail?.images?.length ? detail.images : line.image ? [line.image] : [];
  const highlights = detail?.highlights ?? [];
  const specs = detail?.specifications ?? {};
  const off = discountPct(price, mrp);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-6"
        onClick={onClose}
        role="dialog"
        aria-modal="true"
        aria-label={name}
      >
        <motion.div
          initial={{ y: 30, opacity: 0, scale: 0.98 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          exit={{ y: 20, opacity: 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 26 }}
          onClick={(e) => e.stopPropagation()}
          className="scroll-thin max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-t-2xl border border-line bg-surface shadow-soft sm:rounded-2xl"
        >
          {/* Header */}
          <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-line bg-surface/90 px-5 py-4 backdrop-blur-xl">
            <div className="min-w-0">
              {brand && <p className="text-xs font-medium text-accent">{brand}</p>}
              <h2 className="truncate text-base font-semibold">{name}</h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line text-muted transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <X size={16} />
            </button>
          </div>

          {loading && (
            <div className="flex items-center gap-2 px-5 py-4 text-sm text-muted">
              <Loader2 size={15} className="animate-spin text-accent" /> Loading product…
            </div>
          )}

          <div className="grid grid-cols-1 gap-5 p-5 md:grid-cols-2">
            {/* Showcase */}
            <div>
              <div className="grid aspect-square w-full place-items-center overflow-hidden rounded-xl border border-line bg-white">
                {images[activeImg] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={images[activeImg]} alt={name} className="h-full w-full object-contain" />
                ) : (
                  <span className="text-sm text-muted">No image</span>
                )}
              </div>
              {images.length > 1 && (
                <div className="scroll-thin mt-2 flex gap-2 overflow-x-auto pb-1">
                  {images.map((src, i) => (
                    <button
                      key={src + i}
                      type="button"
                      onClick={() => setActiveImg(i)}
                      className={`grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-lg border bg-white transition-colors ${
                        i === activeImg ? "border-accent" : "border-line"
                      }`}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={src} alt="" className="h-full w-full object-contain" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Price + rating + highlights */}
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold tabular-nums">{money(price)}</span>
                {off > 0 && (
                  <>
                    <span className="text-sm text-muted line-through">{money(mrp!)}</span>
                    <span className="text-sm font-semibold text-good">{off}% off</span>
                  </>
                )}
              </div>
              {rating > 0 && (
                <div className="mt-1.5 flex items-center gap-1.5 text-sm">
                  <span className="inline-flex items-center gap-1 rounded-md bg-good/15 px-1.5 py-0.5 font-semibold text-good">
                    <Star size={12} className="fill-current" /> {rating}
                  </span>
                  {reviews > 0 && <span className="text-muted">{reviews.toLocaleString("en-IN")} ratings</span>}
                </div>
              )}

              {highlights.length > 0 && (
                <div className="mt-4">
                  <h3 className="mb-2 text-sm font-semibold">Highlights</h3>
                  <ul className="space-y-1.5">
                    {highlights.map((h, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-muted">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                        <span>{h}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Specifications */}
          {Object.keys(specs).length > 0 && (
            <div className="px-5 pb-5">
              <h3 className="mb-2 text-sm font-semibold">Specifications</h3>
              <div className="overflow-hidden rounded-xl border border-line">
                {Object.entries(specs).map(([k, v], i) => (
                  <div
                    key={k}
                    className={`grid grid-cols-3 gap-3 px-3 py-2 text-sm ${i % 2 ? "bg-elevated/40" : ""}`}
                  >
                    <span className="text-muted">{k}</span>
                    <span className="col-span-2 break-words">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!loading && !detail && (
            <p className="px-5 pb-4 text-xs text-muted">
              Full details aren&apos;t available for this live listing — showing the summary above.
            </p>
          )}

          <div className="flex items-center gap-1.5 border-t border-line px-5 py-3 text-[11px] text-muted">
            <Eye size={12} /> View only — reviewing a product doesn&apos;t change your order or payment.
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
