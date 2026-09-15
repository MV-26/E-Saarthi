from fastapi import FastAPI

from fastapi import FastAPI, Depends

from pydantic import BaseModel

import os

import requests

from database import engine, Base, User, Session, EmergencyContact

from security import hash_password, verify_password, create_access_token, get_current_user

from dotenv import load_dotenv

load_dotenv()

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class RouteRequest(BaseModel):
    current_latitude: float
    current_longitude: float
    destination_latitude: float
    destination_longitude: float

class EmergencyContactCreate(BaseModel):
    name: str
    phone: str
    relation: str | None = None

def get_risk_level(safety_score: float):
    if safety_score >= 80:
        return "Low"
    elif safety_score >= 60:
        return "Medium"
    else:
        return "High"

def get_weather_score(latitude: float, longitude: float):
    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key:
        return 70, {"status": "Weather API key not configured"}

    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "lat": latitude,
        "lon": longitude,
        "appid": api_key,
        "units": "metric"
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return 70, {
                "status": "Weather API error",
                "status_code": response.status_code,
                "details": response.text
            }
        weather = response.json()

        condition = weather["weather"][0]["main"].lower()
        temperature = weather["main"]["temp"]
        visibility = weather.get("visibility", 10000)
        rain_1h = weather.get("rain", {}).get("1h", 0)

        if condition == "clear":
            score = 95
        elif condition == "clouds":
            score = 85
        elif condition in ["mist", "fog", "haze", "smoke", "dust", "sand", "ash"]:
            score = 70
        elif condition in ["rain", "drizzle"]:
            score = 60
        elif condition == "thunderstorm":
            score = 35
        else:
            score = 70

        if rain_1h >= 10:
            score -= 15
        elif rain_1h >= 5:
            score -= 10

        if visibility < 2000:
            score -= 15
        elif visibility < 5000:
            score -= 5

        score = max(0, min(100, score))

        return round(score, 2), {
            "condition": condition,
            "temperature_c": temperature,
            "rain_1h_mm": rain_1h,
            "visibility_m": visibility
        }

    except Exception:
        return 70, {"status": "Weather service error"}

def get_demo_safety_factors(route_id):
    """
    Temporary demo values.
    Later these values will come from real crime,
    traffic, weather, road and accident data.
    """

    demo_factors = {
        1: {
            "crime_score": 90,
            "traffic_score": 70,
            "weather_score": 90,
            "road_score": 85,
            "accident_score": 80
        },
        2: {
            "crime_score": 75,
            "traffic_score": 85,
            "weather_score": 90,
            "road_score": 75,
            "accident_score": 70
        },
        3: {
            "crime_score": 55,
            "traffic_score": 80,
            "weather_score": 85,
            "road_score": 60,
            "accident_score": 45
        }
    }

    return demo_factors.get(
        route_id,
        {
            "crime_score": 70,
            "traffic_score": 70,
            "weather_score": 70,
            "road_score": 70,
            "accident_score": 70
        }
    )

def calculate_safety_score(
    crime_score: float,
    traffic_score: float,
    weather_score: float,
    road_score: float,
    accident_score: float
):
    score = (
        crime_score * 0.30 +
        traffic_score * 0.20 +
        weather_score * 0.15 +
        road_score * 0.20 +
        accident_score * 0.15
    )

    return round(score, 2)

def select_route_options(routes):
    if not routes:
        return {
            "safest": None,
            "balanced": None,
            "fastest": None
        }

    safest = max(routes, key=lambda r: r["safety_score"])

    fastest = min(routes, key=lambda r: r["duration_minutes"])

    min_duration = min(r["duration_minutes"] for r in routes)
    max_duration = max(r["duration_minutes"] for r in routes)

    if max_duration == min_duration:
        balanced = safest
    else:
        for route in routes:
            time_score = (
                (max_duration - route["duration_minutes"])
                / (max_duration - min_duration)
            ) * 100

            route["balanced_score"] = round(
                route["safety_score"] * 0.6
                + time_score * 0.4, 2
            )

        balanced = max(routes, key=lambda r: r["balanced_score"])

    return {
        "safest": safest["route_id"],
        "balanced": balanced["route_id"],
        "fastest": fastest["route_id"]
    }

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

@app.post("/routes")
def get_routes(route_data: RouteRequest):

    ors_api_key = os.getenv("ORS_API_KEY")

    if not ors_api_key:
        return {"error": "ORS API key is not configured"}

    url = "https://api.heigit.org/openrouteservice/v2/directions/driving-car"

    headers = {
        "Authorization": ors_api_key,
        "Content-Type": "application/json"
    }

    data = {
        "coordinates": [
            [
                route_data.current_longitude,
                route_data.current_latitude
            ],
            [
                route_data.destination_longitude,
                route_data.destination_latitude
            ]
        ],
        "alternative_routes": {
            "target_count": 3,
            "share_factor": 0.8,
            "weight_factor": 2
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=data
    )

    if response.status_code != 200:
        return {
            "error": "Unable to get routes",
            "status_code": response.status_code,
            "details": response.text
        }

    result = response.json()

    routes = []

    for index, route in enumerate(result.get("routes", []), start=1):
        weather_score, weather_info = get_weather_score(
            route_data.destination_latitude,
            route_data.destination_longitude
        )
        safety_factors = get_demo_safety_factors(index)
        safety_factors["weather_score"] = weather_score
        safety_score = calculate_safety_score(
            crime_score=safety_factors["crime_score"],
            traffic_score=safety_factors["traffic_score"],
            weather_score=safety_factors["weather_score"],
            road_score=safety_factors["road_score"],
            accident_score=safety_factors["accident_score"]
        )

        risk_level = get_risk_level(safety_score)

        routes.append({
            "route_id": index,
            "distance_km": round(
                route["summary"]["distance"] / 1000, 2
            ),
            "duration_minutes": round(
                route["summary"]["duration"] / 60
            ),
            "safety_score": safety_score,
            "risk_level": risk_level,
            "safety_factors": safety_factors,
            "weather_info": weather_info,
            "geometry": route["geometry"]
       })

    route_options = select_route_options(routes)

    return {
        "routes": routes,
        "recommended_routes": route_options
    }
    
@app.get("/profile")
def profile(user_id: str = Depends(get_current_user)):
    return {
        "message": "Token is valid",
        "user_id": user_id
    }

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

@app.post("/emergency-contacts")
def add_emergency_contact(
    contact_data: EmergencyContactCreate,
    user_id: str = Depends(get_current_user)
):
    db = Session()

    contact = EmergencyContact(
        user_id=int(user_id),
        name=contact_data.name,
        phone=contact_data.phone,
        relation=contact_data.relation
    )

    db.add(contact)
    db.commit()
    db.refresh(contact)
    db.close()

    return {
        "message": "Emergency contact added successfully",
        "contact_id": contact.id
    }

@app.get("/emergency-contacts")
def get_emergency_contacts(
    user_id: str = Depends(get_current_user)
):
    db = Session()

    contacts = db.query(EmergencyContact).filter(
        EmergencyContact.user_id == int(user_id)
    ).all()

    result = []

    for contact in contacts:
        result.append({
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "relation": contact.relation
        })

    db.close()

    return result