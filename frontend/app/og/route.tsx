import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";
import { site } from "@/lib/site";

// Brand tokens duplicated here (not read from globals.css) — ImageResponse
// renders with Satori, which can't consume CSS custom properties.
const NAVY_950 = "#060e1c";
const NAVY_800 = "#0f2445";
const ORANGE_500 = "#f5820a";
const ORANGE_300 = "#ffbf73";
const SILVER_300 = "#cdd6dd";

const TYPE_LABELS: Record<string, string> = {
  product: "Product",
  products: "Products",
  category: "Category",
  guide: "Buyer's Guide",
  about: "About",
  contact: "Contact",
};

// Node runtime (default) — this is self-hosted in Docker, not deployed to an
// edge network, and Node guarantees process.env is read at request time.
export async function GET(req: NextRequest) {
  const title = req.nextUrl.searchParams.get("title")?.slice(0, 120) || site.name;
  const typeParam = req.nextUrl.searchParams.get("type") ?? "";
  const typeLabel = TYPE_LABELS[typeParam];

  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundImage: `linear-gradient(135deg, ${NAVY_950} 0%, ${NAVY_800} 55%, #204580 100%)`,
          color: "#ffffff",
          padding: "64px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: 32, fontWeight: 800, letterSpacing: 4, color: ORANGE_500 }}>
            {site.shortName.toUpperCase()}
          </span>
          <span style={{ fontSize: 18, letterSpacing: 6, textTransform: "uppercase", color: SILVER_300 }}>
            {site.tagline}
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {typeLabel && (
            <span
              style={{
                display: "flex",
                alignSelf: "flex-start",
                fontSize: 22,
                fontWeight: 700,
                letterSpacing: 2,
                textTransform: "uppercase",
                color: NAVY_950,
                background: ORANGE_300,
                padding: "6px 18px",
                borderRadius: 999,
              }}
            >
              {typeLabel}
            </span>
          )}
          <div style={{ display: "flex", fontSize: 56, fontWeight: 700, lineHeight: 1.2, maxWidth: 1000 }}>
            {title}
          </div>
        </div>
        <div style={{ display: "flex", fontSize: 22, color: SILVER_300 }}>
          {site.regions.join(" · ")}
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}
