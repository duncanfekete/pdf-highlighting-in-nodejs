# Pdf Highlighting in Node.js
This is a working example of dynamically highlighting sections of a pdf on a node.js front end, based on text bounding boxes extracted through google cloud's Document AI OCR.

# Front End

## Requirements to Run Front End (using example pdf/bboxes)
1. pnpm Node.js package manager installed in your directory
2. pdfjs-dist library (js)

## How to Run Front End
1. Ensure document.pdf, and bboxes.json files are in the "public" file directory
2. In the terminal, ensure you're in the same directory as pnpm is setup, then run: pnpm dev
3. Open the web address displayed in the terminal
4. Select BBoxes on the left and see them highlighted on the right

# Back End

## Requirements to Run Back End
1. Google Cloud Account
2. Document AI OCR Processor created in Google Cloud
3. Installed fitz and google libraries (python)

## How to Run Back end
1. In terminal run the python file inject_bboxes_to_frontend, with the relative path address. This will look like:

  python ./inject_bboxes_to_frontend.py PDFs/example_pdf.pdf

This will create the bboxes.json and document.pdf in the frontend "public" file directory
