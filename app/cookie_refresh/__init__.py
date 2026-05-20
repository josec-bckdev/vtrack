"""
cookie_refresh — zero-AI programmed login flow integrated into the vtrack API.

Public surface:
    run_refresh(collection_manager) -> bool
        Loads programmed_steps.json, runs the VNC browser automation,
        and writes the resulting cookies directly onto collection_manager.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace

from app.cookie_refresh.adapters.script_store import FileProgrammedScriptStore
from app.cookie_refresh.adapters.vnc_browser import VncBrowserGateway
from app.cookie_refresh.adapters.direct_vtrack import DirectVtrackGateway
from app.cookie_refresh.application.no_agent_steps import NoAgentStepsUseCase
from app.cookie_refresh.settings import cookie_refresh_settings

if TYPE_CHECKING:
    from app.scraper_async import AsyncCollectionManager

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

_LOGIN_URL = "https://www.rutasljrj.net/rastreo/ljrj/login"


async def run_refresh(collection_manager: "AsyncCollectionManager") -> bool:
    """Load script, spin up VNC browser, run programmed steps, return success."""
    s = cookie_refresh_settings

    store = FileProgrammedScriptStore(s.programmed_steps_path)
    script = await store.load()
    if script is None:
        logger.error("programmed_steps.json not found at %s — cannot refresh cookies", s.programmed_steps_path)
        return False

    browser = VncBrowserGateway(
        base_url=s.vnc_browser_url,
        container_name=s.vnc_container_name,
        container_image=s.vnc_container_image,
        container_network=s.vnc_container_network,
    )
    vtrack = DirectVtrackGateway(collection_manager)

    use_case = NoAgentStepsUseCase(
        browser=browser,
        vtrack=vtrack,
        script=script,
        login_url=_LOGIN_URL,
        login_email=s.login_email,
        login_password=s.login_password,
    )

    with _tracer.start_as_current_span("cookie_refresh.run") as span:
        result = await use_case.execute()
        span.set_attribute("refresh.success", result.success)
        span.set_attribute("refresh.steps_taken", result.steps_taken)

    if result.success:
        logger.info("Cookie refresh succeeded in %d steps", result.steps_taken)
    else:
        logger.error("Cookie refresh failed after %d steps: %s", result.steps_taken, result.error)
    return result.success
