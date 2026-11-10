from pydantic import BaseModel, EmailStr


class User(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str