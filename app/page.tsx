"use client";

import { useEffect, useRef, useState } from "react";
import { renderPDF, PageOffset } from "../components/render_pdf";
import RenderListOfBBoxes, { BBox } from "../components/render_list_of_bboxes";

const SEGMENTATION_COLORS: Record<string, string> = {
  block: "rgba(59, 130, 246, 0.8)",
  paragraph: "rgba(16, 185, 129, 0.8)",
  line: "rgba(245, 158, 11, 0.8)",
  table: "rgba(139, 92, 246, 0.8)",
  table_header_row: "rgba(236, 72, 153, 0.8)",
  table_row: "rgba(239, 68, 68, 0.8)",
  table_cell: "rgba(249, 115, 22, 0.8)",
};

export default function Home() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [pageOffsets, setPageOffsets] = useState<PageOffset[]>([]);
  const [bboxes, setBboxes] = useState<BBox[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Load PDF + BBoxes once on mount
  useEffect(() => {
    // Fetch bboxes
    fetch("/bboxes.json")
      .then((r) => {
        if (!r.ok) throw new Error(`bboxes.json not found (${r.status})`);
        return r.json();
      })
      .then((data: BBox[]) => setBboxes(data))
      .catch((e) => setError(String(e)));

    // Render PDF
    if (!canvasRef.current) return;
    renderPDF(canvasRef.current, "/document.pdf")
      .then(({ width, height, pageOffsets }) => {
        setCanvasSize({ width, height });
        setPageOffsets(pageOffsets);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // Keep overlay canvas in sync with PDF canvas size
  useEffect(() => {
    if (!overlayRef.current || canvasSize.width === 0) return;
    overlayRef.current.width = canvasSize.width;
    overlayRef.current.height = canvasSize.height;
  }, [canvasSize]);

  function handleSelect(bbox: BBox) {
    const overlay = overlayRef.current;
    if (!overlay || canvasSize.width === 0) return;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, overlay.width, overlay.height);

    const [pageNum, x0, y0, x1, y1] = bbox.position;
    const color = SEGMENTATION_COLORS[bbox.segmentation] ?? "rgba(255,255,255,0.8)";

    const pageMeta = pageOffsets[pageNum - 1];
    if (!pageMeta) return;

    const rx = x0 * pageMeta.width;
    const ry = pageMeta.y + y0 * pageMeta.height;
    const rw = (x1 - x0) * pageMeta.width;
    const rh = (y1 - y0) * pageMeta.height;

    ctx.fillStyle = color.replace("0.8", "0.15");
    ctx.fillRect(rx, ry, rw, rh);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.strokeRect(rx, ry, rw, rh);
  }

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        backgroundColor: "#0f172a",
        color: "#e2e8f0",
        fontFamily: "monospace",
        overflow: "hidden",
      }}
    >
      {/* Left panel — BBox list */}
      <div
        style={{
          width: 380,
          minWidth: 380,
          borderRight: "1px solid #1e293b",
          overflowY: "auto",
          padding: 8,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 700, color: "#94a3b8", padding: "8px 4px 4px" }}>
          BBOX TREE
        </div>
        {error && (
          <div style={{ fontSize: 11, color: "#f87171", padding: "4px 8px" }}>
            {error}
          </div>
        )}
        {bboxes.length === 0 && !error && (
          <div style={{ fontSize: 11, color: "#475569", padding: "4px 8px" }}>
            Run <code>python inject_bboxes_to_frontend.py &lt;pdf&gt;</code> to load data.
          </div>
        )}
        <RenderListOfBBoxes bboxes={bboxes} onSelect={handleSelect} />
      </div>

      {/* Right panel — PDF canvas */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "center",
          padding: 24,
        }}
      >
        <div style={{ position: "relative", display: "inline-block" }}>
          <canvas ref={canvasRef} />
          <canvas
            ref={overlayRef}
            style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
          />
        </div>
      </div>
    </div>
  );
}