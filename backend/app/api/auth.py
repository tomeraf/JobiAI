from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.linkedin.client import LinkedInClient, get_linkedin_client
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


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
