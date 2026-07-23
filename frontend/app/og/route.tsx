import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";
import { site } from "@/lib/site";

// Node runtime (default) — this is self-hosted in Docker, not deployed to an
// edge network, and Node guarantees process.env is read at request time.
export async function GET(req: NextRequest) {
  const title = req.nextUrl.searchParams.get("title")?.slice(0, 120) || site.name;

  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#14212b",
          color: "#ffffff",
          padding: "64px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: 32, fontWeight: 800, letterSpacing: 4, color: "#f5a300" }}>
            {site.shortName.toUpperCase()}
          </span>
          <span style={{ fontSize: 18, letterSpacing: 6, textTransform: "uppercase", color: "#b9c4cc" }}>
            {site.tagline}
          </span>
        </div>
        <div style={{ display: "flex", fontSize: 56, fontWeight: 700, lineHeight: 1.2, maxWidth: 1000 }}>
          {title}
        </div>
        <div style={{ display: "flex", fontSize: 22, color: "#b9c4cc" }}>
          {site.regions.join(" · ")}
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}
