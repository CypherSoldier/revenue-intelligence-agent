from pwdlib import PasswordHash
from utils.fake_db import fake_users_db # for local testing, replace with your actual database access code
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from schemas.users import UserInDB
from datetime import datetime, timedelta, timezone
import jwt
from dotenv import load_dotenv
import os

load_dotenv()

password_hash = PasswordHash.recommend()

DUMMY_HASH = password_hash.hash("dummy_password")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        verify_password(password, DUMMY_HASH)
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt