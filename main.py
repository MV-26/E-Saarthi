from fastapi import FastAPI

from database import engine, Base, User, Session

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
def create_user(name: str, email: str, password: str):
    db = Session()

    user = User(
        name=name,
        email=email,
        password=password
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

    db.close()

    return users