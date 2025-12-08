from fastapi import FastAPI
from .common.db.db import init_db, db
from .routes import auth, orgs, settings_users, settings_general, settings_audit_logs, settings_notifications, dashboard, review_listing, upload, debug, claims, debug
from app.common.config import settings
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI(title="EOB → 835")

# # Initialize DB and ensure indices (very minimal)
# db = init_db()

# @app.on_event("startup")
# async def startup_event():
#     # create simple indices for common lookups
#     await db.organizations.create_index("id", unique=True)
#     await db.users.create_index("email", unique=True)
#     await db.organization_memberships.create_index([("org_id", 1), ("user_id", 1)])

#     await db.refresh_tokens.create_index("jti", unique=True)
#     await db.refresh_tokens.create_index("user_id")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database before serving requests
    print(">>> Using JWT SECRET:", settings.JWT_SECRET)
    print("settings object id:", id(settings))

    print(">>> lifespan STARTING")   
    init_db()
    print("MongoDB connection initialized.")
    yield
    # Optional: close DB connection
    # db.client.close()
    print(">>> lifespan ENDING")
    print("Application shutdown.")


app = FastAPI(title="EOB → 835", lifespan=lifespan)


app.include_router(auth.router)
app.include_router(orgs.router)

app.include_router(settings_users.router)
app.include_router(settings_general.router)
app.include_router(settings_audit_logs.router)
app.include_router(settings_notifications.router)

#dashboard
app.include_router(dashboard.router)
app.include_router(review_listing.router)

#upload
app.include_router(upload.router)

#debug
app.include_router(debug.router)

#claims
app.include_router(claims.router)

#template
from .routes import template
app.include_router(template.router)

#generate_835
def _import_generate_835():
    try:
        from .routes import generate_835
        return generate_835
    except ImportError:
        import app.routes.generate_835 as generate_835
        return generate_835
app.include_router(_import_generate_835().router)


origins = []
if settings.CORS_ORIGINS == "*" or not settings.CORS_ORIGINS:
    origins = ["*"]
else:
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ping")
def ping():
    return {"message": "pong"}