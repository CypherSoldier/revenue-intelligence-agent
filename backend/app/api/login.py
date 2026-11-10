from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import os
from dotenv import load_dotenv
from datetime import timedelta
from services.authenticate_user import authenticate_user
from services.authenticate_user import create_access_token
from services.fetch_users import get_current_active_user
from utils.fake_db import fake_users_db
from schemas.auth import Token
from schemas.users import User

router = APIRouter(prefix="/v1/auth", tags=["auth"])

load_dotenv()

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))


@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/users/me/")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    return current_user
