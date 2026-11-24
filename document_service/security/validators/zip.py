import re
import stat
import zipfile

from pathlib import PurePosixPath

from ..config import DEFAULT_CONFIG, SecurityConfig


class ZipSecurityError(Exception):
    pass


class ZipSecurityValidator:

    EXECUTABLE_EXTENSIONS = {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".com",
        ".scr",
        ".vbs",
        ".ps1",
        ".sh",
        ".jar",
    }

    def __init__(
        self,
        config: SecurityConfig = DEFAULT_CONFIG,
    ):
        self.config = config

    def validate(self, zf: zipfile.ZipFile) -> dict:

        checks = {}

        infos = zf.infolist()

        # ------------------------------------------
        # 1. Entry count
        # ------------------------------------------

        checks["entry_count"] = (
            len(infos) <= self.config.max_zip_entries
        )

        if not checks["entry_count"]:
            raise ZipSecurityError("Too many ZIP entries")

        # ------------------------------------------
        # 2. Metadata validation
        # ------------------------------------------

        total_size = 0
        seen_paths = set()

        checks["total_uncompressed_size"] = True
        checks["entry_size"] = True
        checks["compression_ratio"] = True
        checks["path_traversal"] = True
        checks["encrypted_entries"] = True
        checks["symbolic_links"] = True
        checks["duplicate_entries"] = True
        checks["executable_entries"] = True

        for info in infos:

            name = info.filename.replace("\\", "/")
            normalized = PurePosixPath(name)

            # Path traversal and absolute paths.
            if (
                normalized.is_absolute()
                or ".." in normalized.parts
                or name.startswith("/")
                or re.match(r"^[a-zA-Z]:", name)
                or "\x00" in name
            ):
                checks["path_traversal"] = False

                raise ZipSecurityError(
                    f"Unsafe ZIP entry path: {name}"
                )

            # Duplicate normalized paths.
            if name in seen_paths:
                checks["duplicate_entries"] = False

                raise ZipSecurityError(
                    f"Duplicate ZIP entry: {name}"
                )

            seen_paths.add(name)

            # Encrypted entries.
            if info.flag_bits & 0x1:
                checks["encrypted_entries"] = False

                raise ZipSecurityError(
                    f"Encrypted ZIP entry: {name}"
                )

            # Individual entry size.
            if info.file_size > self.config.max_entry_size:
                checks["entry_size"] = False

                raise ZipSecurityError(
                    f"ZIP entry exceeds size limit: {name}"
                )

            total_size += info.file_size

            # Total uncompressed size.
            if total_size > self.config.max_uncompressed_size:
                checks["total_uncompressed_size"] = False

                raise ZipSecurityError(
                    "ZIP uncompressed size exceeds limit"
                )

            # Compression ratio.
            if info.file_size > 0:

                if info.compress_size == 0:
                    checks["compression_ratio"] = False

                    raise ZipSecurityError(
                        f"Invalid compression ratio: {name}"
                    )

                ratio = info.file_size / info.compress_size

                if ratio > self.config.max_compression_ratio:
                    checks["compression_ratio"] = False

                    raise ZipSecurityError(
                        f"Suspicious compression ratio: {name}"
                    )

            # Symbolic links.
            unix_mode = (info.external_attr >> 16) & 0xFFFF

            if stat.S_ISLNK(unix_mode):
                checks["symbolic_links"] = False

                raise ZipSecurityError(
                    f"Symbolic link in ZIP: {name}"
                )

            # Executable files.
            suffix = PurePosixPath(name).suffix.lower()

            if suffix in self.EXECUTABLE_EXTENSIONS:
                checks["executable_entries"] = False

                raise ZipSecurityError(
                    f"Executable file in ZIP: {name}"
                )

        # ------------------------------------------
        # 3. CRC and actual decompressed size
        # ------------------------------------------

        checks["crc_integrity"] = True

        actual_total_size = 0

        for info in infos:

            if info.is_dir():
                continue

            actual_entry_size = 0

            try:
                with zf.open(info, "r") as entry:

                    while True:

                        chunk = entry.read(self.config.chunk_size)

                        if not chunk:
                            break

                        actual_entry_size += len(chunk)
                        actual_total_size += len(chunk)

                        # Enforce actual decompressed size.
                        if actual_entry_size > self.config.max_entry_size:
                            raise ZipSecurityError(
                                f"Actual entry size exceeds limit: "
                                f"{info.filename}"
                            )

                        if actual_total_size > self.config.max_uncompressed_size:
                            raise ZipSecurityError(
                                "Actual ZIP uncompressed size exceeds limit"
                            )

            except ZipSecurityError:
                raise

            except (
                zipfile.BadZipFile,
                RuntimeError,
                NotImplementedError,
                OSError,
            ) as exc:
                checks["crc_integrity"] = False

                raise ZipSecurityError(
                    f"ZIP entry integrity check failed: "
                    f"{info.filename}: {exc}"
                ) from exc

            if actual_entry_size != info.file_size:
                checks["crc_integrity"] = False

                raise ZipSecurityError(
                    f"ZIP entry size mismatch: {info.filename}"
                )

        return checks