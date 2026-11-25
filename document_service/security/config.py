from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityConfig:

    # General
    max_file_size: int = 50 * 1024 * 1024
    chunk_size: int = 1024 * 1024

    # ZIP / Office
    max_zip_entries: int = 5000
    max_uncompressed_size: int = 200 * 1024 * 1024
    max_entry_size: int = 50 * 1024 * 1024
    max_compression_ratio: int = 100

    max_xml_size: int = 20 * 1024 * 1024
    max_sheets: int = 500
    max_rows_per_sheet: int = 100_000
    max_slides: int = 500

    # PDF
    max_pdf_pages: int = 1000
    max_embedded_files: int = 50
    max_form_fields: int = 1000

    # CSV
    max_csv_rows: int = 1_000_000
    max_csv_columns: int = 10_000
    max_csv_field_size: int = 1_000_000

    # Text
    max_text_lines: int = 1_000_000
    max_line_length: int = 100_000

    # HTML
    max_html_tag_count: int = 100_000
    max_html_nesting_depth: int = 500

    # PNG
    max_png_dimension: int = 30_000          # per side (width or height)
    max_png_total_pixels: int = 300_000_000  # width * height cap (~decompression bomb guard)
    max_png_chunks: int = 10_000
    max_png_extra_chunks: int = 1_000_000    # bytes in ancillary (text/metadata) chunks

    # Security policies
    reject_macros: bool = True
    reject_external_relationships: bool = True
    reject_embedded_objects: bool = True
    reject_html_scripts: bool = True         # script/iframe/object/embed/event-handler attrs
    reject_png_metadata: bool = True        # tEXt/iTXt/zTXt chunks allowed by default

    antivirus_enabled: bool = True
    antivirus_required: bool = True


DEFAULT_CONFIG = SecurityConfig()