import logging
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def parse_remote_datetime(date_string: str) -> datetime | None:
    if "0000-00-00" in date_string:
        return None
    try:
        naive_dt = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
        return naive_dt.replace(tzinfo=ZoneInfo("America/Bogota"))
    except ValueError:
        logger.warning(f"Failed to parse datetime: {date_string}")
        return None


def normalize_route_data(valores_data: list, estados_data: list) -> Optional[dict]:
    if not valores_data or not estados_data:
        return None

    first_valores = valores_data[0]
    first_estados = estados_data[0]

    if not first_valores or not first_estados:
        return None

    try:
        return {
            "ruta": int(first_valores[0]),
            "ns_latitude": float(first_valores[2]),
            "ew_longitude": float(first_valores[3]),
            "position_ts": parse_remote_datetime(first_valores[5]),
            "route_status": first_estados[1],
            "route_status_ts": parse_remote_datetime(first_estados[2]),
            "student_status": first_estados[5],
            "student_status_ts": parse_remote_datetime(first_estados[6]),
        }
    except (ValueError, IndexError, TypeError) as e:
        logger.error(f"Error normalizing data: {e}")
        return None


def should_start_collection(normalized_data: dict) -> bool:
    """True when route is active or current time falls in a known collection band."""
    recorrido = normalized_data.get("route_status") == "En recorrido"
    now = datetime.now(ZoneInfo("America/Bogota"))
    in_am_time_band = time(5, 0) <= now.time() <= time(9, 0)
    in_pm_time_band = time(15, 0) <= now.time() <= time(18, 0)
    logger.info(
        f"Collection starting due to: recorrido={recorrido}, "
        f"in_am_time_band={in_am_time_band}, in_pm_time_band={in_pm_time_band}"
    )
    return recorrido or in_am_time_band or in_pm_time_band


def should_stop_collection(normalized_data: dict) -> bool:
    """True when route completion is detected based on student status and hour."""
    student_status = normalized_data.get("student_status", "")
    current_hour = datetime.now(ZoneInfo("America/Bogota")).hour
    pm_delivered = (student_status == "Bajo") and (current_hour > 12)
    am_onboard = (student_status == "Subio") and (current_hour <= 12)
    return pm_delivered or am_onboard
