"""
PNG security check.

Parses the PNG chunk structure directly (no image decoding library needed):
  - Signature + mandatory IHDR header
  - Dimension / total-pixel caps (decompression-bomb guard for renderers)
  - Chunk count and ancillary-chunk (tEXt/iTXt/zTXt) byte limits
  - CRC integrity for every chunk
  - IEND termination
"""

import struct
import zlib

from .base import FileSecurityCheck
from document_service.security.models import SecurityReport, SecurityCheckResult
from document_service.security.config import DEFAULT_CONFIG, SecurityConfig

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Ancillary metadata chunks that can carry arbitrary payloads.
TEXT_CHUNKS = {b"tEXt", b"iTXt", b"zTXt"}

# Chunk types that must never appear before IHDR / after IEND.
MANDATORY_FIRST = b"IHDR"
MANDATORY_LAST = b"IEND"


class PngStructureError(Exception):
    pass


def _iter_chunks(data: bytes):
    """Yield (chunk_type, chunk_data, crc_ok) for each PNG chunk."""
    pos = 8  # skip signature
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]

        chunk_start = pos + 8
        chunk_end = chunk_start + length
        if chunk_end + 4 > len(data):
            raise PngStructureError(
                f"Truncated {ctype.decode('latin-1')} chunk"
            )

        chunk_data = data[chunk_start:chunk_end]
        (stored_crc,) = struct.unpack(">I", data[chunk_end:chunk_end + 4])
        crc_ok = (
            zlib.crc32(ctype + chunk_data) & 0xFFFFFFFF
        ) == stored_crc

        yield ctype, chunk_data, crc_ok
        pos = chunk_end + 4

        if ctype == b"IEND":
            return


class PngSecurityCheck(FileSecurityCheck):
    """Security validation for image/png documents."""

    def __init__(
        self,
        config: SecurityConfig = DEFAULT_CONFIG,
    ):
        super().__init__(config)

    def check(
        self,
        file_path,
        mime_type,
        file_size,
    ):
        base = super().check(
            file_path,
            mime_type,
            file_size,
        )

        if not base.passed:
            return base

        checks = base.checks.copy()
        reasons = []

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            # --- signature -------------------------------------------------
            checks["png_signature"] = data.startswith(PNG_SIGNATURE)
            if not checks["png_signature"]:
                raise PngStructureError("Invalid PNG signature")

            # --- chunk walk ------------------------------------------------
            chunk_count = 0
            text_chunk_bytes = 0
            text_chunk_types = []
            crc_failures = []
            saw_ihdr = False
            saw_iend = False
            header = None

            for ctype, cdata, crc_ok in _iter_chunks(data):
                chunk_count += 1

                if chunk_count > self.config.max_png_chunks:
                    raise PngStructureError("Too many PNG chunks")

                if chunk_count == 1:
                    if ctype != MANDATORY_FIRST:
                        raise PngStructureError("First chunk is not IHDR")
                    saw_ihdr = True
                    if len(cdata) < 13:
                        raise PngStructureError("IHDR too short")
                    width, height = struct.unpack(">II", cdata[:8])
                    header = (width, height)
                elif not saw_ihdr:
                    raise PngStructureError("Data before IHDR chunk")

                if not crc_ok:
                    crc_failures.append(ctype.decode("latin-1"))

                if ctype in TEXT_CHUNKS:
                    text_chunk_bytes += len(cdata)
                    text_chunk_types.append(ctype.decode("latin-1"))

                if ctype == b"IEND":
                    saw_iend = True
                    break

            checks["chunk_structure"] = saw_ihdr and saw_iend
            if not saw_iend:
                reasons.append("Missing IEND chunk (truncated image)")

            checks["crc_integrity"] = not crc_failures
            if crc_failures:
                reasons.append(f"CRC mismatch in chunks: {', '.join(crc_failures[:5])}")

            checks["chunk_limits"] = chunk_count <= self.config.max_png_chunks
            if not checks["chunk_limits"]:
                reasons.append(f"Too many chunks: {chunk_count}")

            # --- dimension caps ----------------------------------------------
            if header:
                width, height = header
                checks["dimensions"] = (
                    width <= self.config.max_png_dimension
                    and height <= self.config.max_png_dimension
                    and width * height <= self.config.max_png_total_pixels
                )
                if not checks["dimensions"]:
                    reasons.append(
                        f"Image dimensions too large: {width}x{height}"
                    )
            else:
                checks["dimensions"] = False
                reasons.append("Missing IHDR dimensions")

            # --- metadata payload policy --------------------------------------
            checks["metadata_size"] = (
                text_chunk_bytes <= self.config.max_png_extra_chunks
            )
            if not checks["metadata_size"]:
                reasons.append(
                    f"Metadata chunks too large: {text_chunk_bytes} bytes "
                    f"({', '.join(text_chunk_types[:5])})"
                )

            if self.config.reject_png_metadata and text_chunk_types:
                checks["metadata_allowed"] = False
                reasons.append(
                    f"Metadata chunks present: {', '.join(sorted(set(text_chunk_types)))}"
                )
            else:
                checks["metadata_allowed"] = True

        except PngStructureError as exc:
            checks["png_structure"] = False
            reasons.append(str(exc))

        except Exception as exc:
            checks["parseable"] = False
            reasons.append(str(exc))

        failed = [key for key, value in checks.items() if not value]

        if failed:
            # Corrupt binary structure = quarantine; policy/limit breaches = fail.
            critical = {"png_signature", "png_structure", "parseable", "crc_integrity"}
            result = (
                SecurityCheckResult.QUARANTINE
                if critical.intersection(failed)
                else SecurityCheckResult.FAIL
            )

            return SecurityReport(
                result=result,
                checks=checks,
                reason="; ".join(reasons) or "PNG validation failed",
                file_path=file_path,
                mime_type=mime_type,
                file_size=file_size,
                sha256=base.sha256,
            )

        return SecurityReport(
            result=SecurityCheckResult.PASS,
            checks=checks,
            file_path=file_path,
            mime_type=mime_type,
            file_size=file_size,
            sha256=base.sha256,
        )
