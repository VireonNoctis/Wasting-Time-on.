import { ImageResponse } from "next/og"
import { rethrowIfFrameworkError } from "@/lib/next-control-flow"
import type { NextRequest } from "next/server"

const DEFAULT_ACCENT = "#3b82f6" // blue accent for anime
const TYPE_LABEL = "ANIME"
const LUNAR_LOGO_URL = "https://files.catbox.moe/rl48xt.png"

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url)

    // Example call:
    // /api/anime-embed?title=Your+Title&cover=...&banner=...&tags=Action|Fantasy|Ongoing&themecolor=3b82f6
    const title = searchParams.get("title") || "Untitled"
    const coverUrl = searchParams.get("cover")
    const bannerUrl = searchParams.get("banner")
    const tagsParam = searchParams.get("tags") || ""
    const themeParam = searchParams.get("themecolor")

    const accent = themeParam
      ? themeParam.startsWith("#")
        ? themeParam
        : `#${themeParam}`
      : DEFAULT_ACCENT

    const tags = tagsParam
      .split("|")
      .map((t) => t.trim())
      .filter(Boolean)

    return new ImageResponse(
      (
        <div
          style={{
            display: "flex",
            width: "1920px",
            height: "1080px",
            backgroundColor: "#050505",
            fontFamily: "system-ui, sans-serif",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Background banner layer */}
          {bannerUrl && (
            <img
              src={bannerUrl}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
                filter: "blur(6px)",
                opacity: 0.35,
              }}
            />
          )}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: `linear-gradient(120deg, rgba(5, 5, 5, 0.92), rgba(5, 5, 5, 0.75)), radial-gradient(circle at 75% 25%, ${accent}33, transparent 60%)`,
            }}
          />

          {/* Left: text content */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              width: "1120px",
              padding: "80px",
              position: "relative",
            }}
          >
            {/* Type badge */}
            <div
              style={{
                display: "flex",
                alignSelf: "flex-start",
                padding: "10px 28px",
                borderRadius: "999px",
                border: `2px solid ${accent}`,
                color: accent,
                fontSize: "28px",
                fontWeight: 700,
                letterSpacing: "0.08em",
              }}
            >
              {TYPE_LABEL}
            </div>

            {/* Title + tags block */}
            <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
              <div
                style={{
                  display: "flex",
                  fontSize: "72px",
                  fontWeight: 800,
                  color: "#ffffff",
                  lineHeight: 1.15,
                  letterSpacing: "-0.02em",
                }}
              >
                {title}
              </div>

              {tags.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "16px", maxWidth: "900px" }}>
                  {tags.map((tag, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        padding: "10px 22px",
                        borderRadius: "10px",
                        background: "rgba(255, 255, 255, 0.06)",
                        border: "1px solid rgba(255, 255, 255, 0.12)",
                        color: "rgba(255, 255, 255, 0.75)",
                        fontSize: "26px",
                        fontWeight: 500,
                      }}
                    >
                      {tag}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer: logo + wordmark */}
            <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
              <img
                src={LUNAR_LOGO_URL}
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "50%",
                  objectFit: "cover",
                  border: `2px solid ${accent}`,
                }}
              />
              <div style={{ display: "flex", flexDirection: "column" }}>
                <div style={{ display: "flex", fontSize: "32px", fontWeight: 700, color: "#ffffff" }}>
                  Lunar
                </div>
                <div style={{ display: "flex", fontSize: "22px", color: "rgba(255, 255, 255, 0.5)" }}>
                  lunarx.to
                </div>
              </div>
            </div>
          </div>

          {/* Right: cover art */}
          <div
            style={{
              display: "flex",
              width: "800px",
              height: "1080px",
              position: "relative",
            }}
          >
            {coverUrl ? (
              <img
                src={coverUrl}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            ) : (
              <div
                style={{
                  display: "flex",
                  width: "100%",
                  height: "100%",
                  background: `linear-gradient(160deg, ${accent}33, #0a0a0a)`,
                }}
              />
            )}
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                bottom: 0,
                width: "200px",
                background: "linear-gradient(to right, #050505, transparent)",
              }}
            />
          </div>
        </div>
      ),
      {
        width: 1920,
        height: 1080,
      }
    )
  } catch (error) {
    rethrowIfFrameworkError(error)
    console.error(error)
    return new Response("Failed to generate image", { status: 500 })
  }
}
