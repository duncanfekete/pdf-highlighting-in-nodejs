"use client";

import { useState } from "react";

// Matches the Python BBox dataclass from google_ocr.py
// position = (page, x0, y0, x1, y1) — normalized 0..1 coords
export interface BBox {
  id: string;
  text: string;
  position: [number, number, number, number, number];
  segmentation: string;
  children: BBox[];
}

interface BBoxItemProps {
  bbox: BBox;
  depth: number;
  selectedId: string | null;
  onSelect: (bbox: BBox) => void;
}

function BBoxItem({ bbox, depth, selectedId, onSelect }: BBoxItemProps) {
  const [expanded, setExpanded] = useState(true);
  const isSelected = selectedId === bbox.id;
  const hasChildren = bbox.children.length > 0;
  const [page, x0, y0, x1, y1] = bbox.position;

  return (
    <div style={{ paddingLeft: depth * 16 }}>
      <div
        onClick={() => onSelect(bbox)}
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 2,
          padding: "4px 8px",
          marginBottom: 2,
          borderRadius: 4,
          cursor: "pointer",
          backgroundColor: isSelected ? "#1e40af" : depth % 2 === 0 ? "#1e293b" : "#0f172a",
          borderLeft: `3px solid ${isSelected ? "#60a5fa" : "transparent"}`,
          userSelect: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {hasChildren && (
            <span
              onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
              style={{ fontSize: 10, color: "#94a3b8", minWidth: 10 }}
            >
              {expanded ? "▾" : "▸"}
            </span>
          )}
          <span style={{ fontSize: 11, fontWeight: 600, color: "#93c5fd" }}>
            {bbox.segmentation}
          </span>
          {bbox.text && (
            <span style={{ fontSize: 11, color: "#e2e8f0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 300 }}>
              {bbox.text}
            </span>
          )}
        </div>
        <div style={{ fontSize: 10, color: "#64748b", paddingLeft: hasChildren ? 18 : 0 }}>
          <span>id: {bbox.id}</span>
          {"  ·  "}
          <span>p{page} [{x0.toFixed(3)}, {y0.toFixed(3)}, {x1.toFixed(3)}, {y1.toFixed(3)}]</span>
        </div>
      </div>

      {hasChildren && expanded && (
        <div>
          {bbox.children.map((child) => (
            <BBoxItem
              key={child.id}
              bbox={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface RenderListOfBBoxesProps {
  bboxes: BBox[];
  onSelect?: (bbox: BBox) => void;
}

export default function RenderListOfBBoxes({ bboxes, onSelect }: RenderListOfBBoxesProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  function handleSelect(bbox: BBox) {
    setSelectedId(bbox.id);
    onSelect?.(bbox);
  }

  return (
    <div
      style={{
        fontFamily: "monospace",
        backgroundColor: "#0f172a",
        color: "#e2e8f0",
        padding: 8,
        borderRadius: 6,
        overflowY: "auto",
        maxHeight: "80vh",
      }}
    >
      {bboxes.length === 0 ? (
        <div style={{ color: "#475569", padding: 8 }}>No bboxes to display.</div>
      ) : (
        bboxes.map((bbox) => (
          <BBoxItem
            key={bbox.id}
            bbox={bbox}
            depth={0}
            selectedId={selectedId}
            onSelect={handleSelect}
          />
        ))
      )}
    </div>
  );
}
