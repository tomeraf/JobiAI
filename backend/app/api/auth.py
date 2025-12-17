from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.linkedin.auth import LinkedInAuth
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
    auth = LinkedInAuth()

    try:
        is_logged_in = await auth.check_session()

        if is_logged_in:
            profile = await auth.get_profile_info()
            return AuthStatus(
                logged_in=True,
                name=profile.get("name"),
                email=profile.get("email"),
                message="LinkedIn session is active",
            )
        else:
            return AuthStatus(
                logged_in=False,
                message="Not logged in to LinkedIn. Use /api/auth/login with email and password.",
            )
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return AuthStatus(
            logged_in=False,
            message=f"Error checking session: {str(e)}",
        )


@router.post("/login", response_model=AuthStatus)
async def start_login(request: LoginRequest):
    """
    Login to LinkedIn with email and password.
    Credentials will be saved for future use.
    """
    auth = LinkedInAuth()

    try:
        logger.info(f"Starting LinkedIn login for: {request.email}")
        success = await auth.login(request.email, request.password)

        if success:
            profile = await auth.get_profile_info()
            return AuthStatus(
                logged_in=True,
                name=profile.get("name"),
                email=profile.get("email"),
                message="Successfully logged in to LinkedIn!",
            )
        else:
            return AuthStatus(
                logged_in=False,
                message="Login failed. Please check your credentials.",
            )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Login failed: {str(e)}",
        )


@router.post("/login-browser", response_model=AuthStatus)
async def login_with_browser():
    """
    Open a browser window for manual LinkedIn login.

    This will open a browser, let you login manually,
    then capture and save the cookies for future API use.
    """
    auth = LinkedInAuth()

    try:
        logger.info("Starting browser login flow...")
        success = await auth.login_with_browser()

        if success:
            profile = await auth.get_profile_info()
            return AuthStatus(
                logged_in=True,
                name=profile.get("name"),
                email=profile.get("email"),
                message="Successfully logged in! Cookies saved for future use.",
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
    """Clear saved LinkedIn session and credentials."""
    auth = LinkedInAuth()

    try:
        await auth.clear_session()
        return {"message": "LinkedIn session cleared"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Logout failed: {str(e)}",
        )
