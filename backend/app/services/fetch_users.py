from fastapi import Depends, FastAPI, HTTPException, status
from typing import Annotated
import jwt
from jwt.exceptions import InvalidTokenError
import os
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from schemas.auth import TokenData
from schemas.users import User
from authenticate_user import get_user
from utils.fake_db import fake_users_db

load_dotenv()

ALGORITHM = os.getenv("ALGORITHM")
SECRET_KEY = os.getenv("SECRET_KEY")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user