from fastapi import FastAPI

from pydantic import BaseModel

from database import engine, Base, User, Session

from security import hash_password, verify_password, create_access_token

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

app = FastAPI()

Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {"message": "eSaarthi Backend is Running"}


@app.get("/test-db")
def test_db():
    try:
        with engine.connect() as connection:
            return {"message": "PostgreSQL Connected Successfully"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/create-user")
def create_user(user_data: UserCreate):
    db = Session()

    hashed_password = hash_password(user_data.password)

    user = User(
    name=user_data.name,
    email=user_data.email,
    password=hashed_password
)

    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    return {
        "message": "User created successfully",
        "user_id": user.id
    }

@app.get("/users")
def get_users():
    db = Session()

    users = db.query(User).all()

    result = []

    for user in users:
        result.append({
            "id": user.id,
            "name": user.name,
            "email": user.email
        })

    db.close()

    return result

@app.post("/login")
def login(user_data: UserLogin):
    db = Session()

    user = db.query(User).filter(User.email == user_data.email).first()

    if not user:
        db.close()
        return {"error": "Invalid email or password"}

    if not verify_password(user_data.password, user.password):
        db.close()
        return {"error": "Invalid email or password"}

    access_token = create_access_token({
    "sub": str(user.id),
    "email": user.email
})

    db.close()

    return {
        "message": "Login successful",
        "access_token": access_token,
        "user_id": user.id,
        "name": user.name,
        "email": user.email
    }