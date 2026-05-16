"""Settings for the integrated cookie refresh feature."""
import os


class CookieRefreshSettings:
    vnc_browser_url: str = os.environ.get("VNC_BROWSER_URL", "http://vnc-browser:8080")
    vnc_container_name: str = os.environ.get("VNC_CONTAINER_NAME", "vnc_browser")
    programmed_steps_path: str = os.environ.get("PROGRAMMED_STEPS_PATH", "/data/programmed_steps.json")
    login_email: str = os.environ.get("LOGIN_EMAIL", "")
    login_password: str = os.environ.get("LOGIN_PASSWORD", "")
    schedule_morning: str = os.environ.get("COOKIE_REFRESH_SCHEDULE_MORNING", "40 5 * * 1-5")
    schedule_afternoon: str = os.environ.get("COOKIE_REFRESH_SCHEDULE_AFTERNOON", "10 15 * * 1-5")
    timezone: str = "America/Bogota"


cookie_refresh_settings = CookieRefreshSettings()
