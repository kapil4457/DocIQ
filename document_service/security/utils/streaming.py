import hashlib
import os

from dataclasses import dataclass


@dataclass
class StreamInspection:

    file_size: int
    sha256: str
    header: bytes


def inspect_file_stream(
    file_path: str,
    max_size: int,
    chunk_size: int = 1024 * 1024,
) -> StreamInspection:

    digest = hashlib.sha256()

    total_size = 0
    header = bytearray()

    with open(file_path, "rb") as f:

        while True:

            chunk = f.read(chunk_size)

            if not chunk:
                break

            total_size += len(chunk)

            if total_size > max_size:
                raise ValueError(
                    f"File exceeds maximum size of {max_size} bytes"
                )

            digest.update(chunk)

            if len(header) < 16:

                remaining = 16 - len(header)

                header.extend(chunk[:remaining])

    actual_size = os.path.getsize(file_path)

    if actual_size != total_size:
        raise ValueError("File changed during inspection")

    return StreamInspection(
        file_size=total_size,
        sha256=digest.hexdigest(),
        header=bytes(header),
    )