from pathlib import Path
import pdfplumber
import argparse
import csv
import re
from PIL import Image
import io

class PDFToTextConverter:
    def __init__(self, input_path, output_folder, convert_images=False, convert_tables=False):
        self.input_path = Path(input_path)
        self.output_folder = Path(output_folder)
        self.convert_images = convert_images
        self.convert_tables = convert_tables

    def convert_pdf_to_text(self, pdf_path):
        with pdfplumber.open(str(pdf_path)) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() or ''
            return text

    def save_text(self, text, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)

    def save_table(self, table, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for row in table:
                writer.writerow(row)

    def save_image(self, image, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)

    def find_caption(self, page, bbox, max_lines=2):
        # Search both above and below the bbox for a caption
        x0, top, x1, bottom = bbox
        search_areas = [
            (x0, max(0, top-40), x1, top),  # above
            (x0, bottom, x1, min(page.height, bottom+40))  # below
        ]
        for area in search_areas:
            try:
                text = page.within_bbox(area).extract_text() or ''
            except ValueError:
                # Bounding box has zero area, treat as no caption
                continue
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            for line in lines:
                # Look for 'Table <n>' or 'Fig <n>' (case-insensitive)
                m = re.match(r'(?i)(Table|Fig(?:ure)?)\s*\d+[:.\-\s]*(.*)', line)
                if m:
                    caption = m.group(2).strip()
                    # Clean up for filename
                    caption = re.sub(r'[^\w\-]+', '_', caption)
                    return caption[:40] if caption else None
        return None

    def extract_and_save_from_pdf(self, pdf_path, output_dir):
        with pdfplumber.open(str(pdf_path)) as pdf:
            # Save text
            text = ''
            for page in pdf.pages:
                text += page.extract_text() or ''
            text_path = output_dir / (pdf_path.stem + '.txt')
            self.save_text(text, text_path)
            print(f"Saved text to {text_path}")

            # Extract tables and images
            table_count = 1
            image_count = 1
            for page_num, page in enumerate(pdf.pages, 1):
                # Tables
                if self.convert_tables:
                    tables = page.extract_tables()
                    for table in tables:
                        caption = self.find_caption(page, (0, 0, page.width, page.height))
                        if not caption:
                            caption = f'table_{table_count}'
                        table_path = output_dir / f"{pdf_path.stem}_{caption}_p{page_num}.csv"
                        self.save_table(table, table_path)
                        print(f"Saved table to {table_path}")
                        table_count += 1
                # Images
                if self.convert_images:
                    for img in page.images:
                        x0, top, x1, bottom = img['x0'], img['top'], img['x1'], img['bottom']
                        bbox = (x0, top, x1, bottom)
                        try:
                            cropped = page.within_bbox(bbox).to_image(resolution=300).original
                        except ValueError as e:
                            print(f"Error cropping image: {e}")
                            continue
                        caption = self.find_caption(page, bbox)
                        if not caption:
                            caption = f'figure_{image_count}'
                        img_path = output_dir / f"{pdf_path.stem}_{caption}_p{page_num}.png"
                        self.save_image(cropped, img_path)
                        print(f"Saved image to {img_path}")
                        image_count += 1

    def convert(self):
        if self.input_path.is_file() and self.input_path.suffix.lower() == '.pdf':
            output_dir = self.output_folder
            self.extract_and_save_from_pdf(self.input_path, output_dir)
        elif self.input_path.is_dir():
            subfolder = self.output_folder / self.input_path.name
            for pdf_file in self.input_path.glob('*.pdf'):
                self.extract_and_save_from_pdf(pdf_file, subfolder)
        else:
            print("Invalid file or directory. Please provide a valid PDF file or a folder containing PDF files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert PDF file or all PDFs in a folder to text, images, and tables.")
    parser.add_argument('input_path', type=str, help='Path to a PDF file or a folder of PDF files')
    parser.add_argument('-o', '--output', type=str, default='converted_files', help='Output folder to save files (default: converted_files)')
    parser.add_argument('--convert-images', action='store_true', help='Extract images from the PDF')
    parser.add_argument('--convert-tables', action='store_true', help='Extract tables from the PDF')
    args = parser.parse_args()

    converter = PDFToTextConverter(
        args.input_path,
        args.output,
        convert_images=args.convert_images,
        convert_tables=args.convert_tables
    )
    converter.convert()
