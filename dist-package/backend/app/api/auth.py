from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.linkedin.client import LinkedInClient, get_linkedin_client
from app.services.linkedin.browser_utils import show_browser_window, hide_browser_window
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# --- Settings Models ---

class AppSettingsResponse(BaseModel):
    """Response model for app settings."""
    port: int
    browser_visible: bool
    auto_start: bool
    first_run: bool


class AppSettingsUpdate(BaseModel):
    """Request model for updating settings."""
    browser_visible: Optional[bool] = None
    auto_start: Optional[bool] = None


class AuthStatus(BaseModel):
    logged_in: bool
    email: str | None = None
    name: str | None = None
    message: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.get("/status", response_model=AuthStatus)
async def check_auth_status():
    """Check if we have a valid LinkedIn session."""
    client = get_linkedin_client()

    try:
        is_logged_in = await client.check_session()

        if is_logged_in:
            profile = await client.get_profile_info()
            return AuthStatus(
                logged_in=True,
                name=profile.get("name"),
                email=profile.get("email"),
                message="LinkedIn session is active",
            )
        else:
            return AuthStatus(
                logged_in=False,
                message="Not logged in to LinkedIn. Use /api/auth/login-browser to login.",
            )
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return AuthStatus(
            logged_in=False,
            message=f"Error checking session: {str(e)}",
        )


@router.post("/login-browser", response_model=AuthStatus)
async def login_with_browser():
    """
    Open a browser window for manual LinkedIn login.

    This will open a browser, let you login manually,
    then capture and save the cookies for future API use.
    """
    client = get_linkedin_client()

    try:
        logger.info("Starting browser login flow...")
        success = await client.login_with_browser()

        if success:
            profile = await client.get_profile_info()
            return AuthStatus(
                logged_in=True,
                name=profile.get("name"),
                email=profile.get("email"),
                message="Successfully logged in! Session saved for future use.",
            )
        else:
            return AuthStatus(
                logged_in=False,
                message="Browser login failed or was cancelled.",
            )
    except Exception as e:
        logger.error(f"Browser login error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Browser login failed: {str(e)}",
        )


@router.post("/logout")
async def logout():
    """Clear saved LinkedIn session."""
    client = get_linkedin_client()

    try:
        await client.logout()
        return {"message": "LinkedIn session cleared"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Logout failed: {str(e)}",
        )


# --- Settings Endpoints ---

@router.get("/settings", response_model=AppSettingsResponse)
async def get_settings():
    """Get current application settings."""
    try:
        from app.settings import get_settings as get_app_settings
        settings = get_app_settings()
        return AppSettingsResponse(
            port=settings.port,
            browser_visible=settings.browser_visible,
            auto_start=settings.auto_start,
            first_run=settings.first_run,
        )
    except RuntimeError:
        # Settings not initialized (dev mode)
        return AppSettingsResponse(
            port=9000,
            browser_visible=True,
            auto_start=False,
            first_run=False,
        )


@router.put("/settings", response_model=AppSettingsResponse)
async def update_settings(update: AppSettingsUpdate):
    """Update application settings."""
    try:
        from app.settings import get_settings as get_app_settings, save_settings

        settings = get_app_settings()

        if update.browser_visible is not None:
            settings.browser_visible = update.browser_visible
            # Apply browser visibility immediately
            if update.browser_visible:
                show_browser_window()
            else:
                hide_browser_window()

        if update.auto_start is not None:
            settings.auto_start = update.auto_start
            # Update Windows registry
            try:
                from app.tray.autostart import set_autostart
                set_autostart(update.auto_start)
            except Exception as e:
                logger.warning(f"Failed to update autostart: {e}")

        save_settings()

        return AppSettingsResponse(
            port=settings.port,
            browser_visible=settings.browser_visible,
            auto_start=settings.auto_start,
            first_run=settings.first_run,
        )
    except RuntimeError:
        # Settings not initialized (dev mode)
        raise HTTPException(
            status_code=503,
            detail="Settings not available in development mode",
        )


# --- Browser Control Endpoints ---

@router.post("/browser/show")
async def show_browser():
    """Show the browser window (bring to front)."""
    show_browser_window()
    return {"message": "Browser window shown"}


@router.post("/browser/hide")
async def hide_browser():
    """Hide the browser window (move off-screen)."""
    hide_browser_window()
    return {"message": "Browser window hidden"}
