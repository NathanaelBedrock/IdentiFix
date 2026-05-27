from __future__ import annotations
import asyncio
from pathlib import Path
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ExifData

try:
    import exifread
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_GPS_REF_MAP = {"N": 1, "S": -1, "E": 1, "W": -1}


def _rational_to_float(value) -> float:
    try:
        return float(value.num) / float(value.den)
    except Exception:
        return float(str(value))


def _parse_gps(tags: dict, key_deg: str, key_ref: str) -> float | None:
    coord = tags.get(key_deg)
    ref = tags.get(key_ref)
    if not coord or not ref:
        return None
    values = coord.values
    if len(values) < 3:
        return None
    deg = _rational_to_float(values[0])
    mins = _rational_to_float(values[1])
    secs = _rational_to_float(values[2])
    decimal = deg + mins / 60 + secs / 3600
    return decimal * _GPS_REF_MAP.get(str(ref.values), 1)


class ExifReadCollector(BaseCollector):
    name = "exifread"
    requires_image = True

    @classmethod
    def available(cls) -> bool:
        return _AVAILABLE

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        image_path = target.image_path
        loop = asyncio.get_event_loop()

        def _run():
            with open(image_path, "rb") as f:
                return exifread.process_file(f, stop_tag="UNDEF", details=True)

        tags = await loop.run_in_executor(None, _run)

        str_tags = {str(k): str(v) for k, v in tags.items()}
        gps_lat = _parse_gps(tags, "GPS GPSLatitude", "GPS GPSLatitudeRef")
        gps_lon = _parse_gps(tags, "GPS GPSLongitude", "GPS GPSLongitudeRef")

        result.exif_data = ExifData(
            file_path=image_path,
            tags=str_tags,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            camera_make=str_tags.get("Image Make"),
            camera_model=str_tags.get("Image Model"),
            datetime_original=str_tags.get("EXIF DateTimeOriginal"),
        )
