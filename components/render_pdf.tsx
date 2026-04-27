export type PageOffset = { y: number; width: number; height: number };

/** Renders all pages of a PDF onto the provided canvas element, stacked vertically.
 *  @param canvas  The canvas to draw into.
 *  @param source  A URL string (e.g. "/document.pdf") or a Uint8Array of raw PDF bytes.
 *  @param scale   Render scale (default 1.5).
 *  @returns The total canvas { width, height } and per-page offsets.
 */
export async function renderPDF(
  canvas: HTMLCanvasElement,
  source: string | Uint8Array,
  scale = 1.5
): Promise<{ width: number; height: number; pageOffsets: PageOffset[] }> {
  const { getDocument, GlobalWorkerOptions } = await import("pdfjs-dist");
  GlobalWorkerOptions.workerSrc =
    "https://unpkg.com/pdfjs-dist@5.6.205/build/pdf.worker.min.mjs";

  const loadParam =
    typeof source === "string" ? { url: source } : { data: source };

  const pdf = await getDocument(loadParam).promise;
  const numPages = pdf.numPages;
  const PAGE_GAP = 8;

  // Render each page to an offscreen canvas first
  type PageData = { offscreen: HTMLCanvasElement; width: number; height: number };
  const pages: PageData[] = [];

  for (let i = 1; i <= numPages; i++) {
    const page = await pdf.getPage(i);
    const viewport = page.getViewport({ scale });

    const offscreen = document.createElement("canvas");
    offscreen.width = viewport.width;
    offscreen.height = viewport.height;
    const ctx = offscreen.getContext("2d");
    if (!ctx) throw new Error("Failed to get offscreen canvas context");

    await page
      .render({
        canvas: null,
        canvasContext: ctx,
        viewport,
      } as import("pdfjs-dist/types/src/display/api").RenderParameters)
      .promise;

    pages.push({ offscreen, width: viewport.width, height: viewport.height });
  }

  const totalHeight =
    pages.reduce((sum, p) => sum + p.height, 0) + PAGE_GAP * (numPages - 1);
  const maxWidth = Math.max(...pages.map((p) => p.width));

  canvas.width = maxWidth;
  canvas.height = totalHeight;

  const context = canvas.getContext("2d");
  if (!context) throw new Error("Failed to get canvas context");

  const pageOffsets: PageOffset[] = [];
  let yOffset = 0;

  for (const p of pages) {
    pageOffsets.push({ y: yOffset, width: p.width, height: p.height });
    context.drawImage(p.offscreen, 0, yOffset);
    yOffset += p.height + PAGE_GAP;
  }

  return { width: maxWidth, height: totalHeight, pageOffsets };
}
