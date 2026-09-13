from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


if __name__ == "__main__":
    password = "test123"
    hashed = hash_password(password)

    print("Original:", password)
    print("Hashed:", hashed)