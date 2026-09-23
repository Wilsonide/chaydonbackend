import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.domains.analytics.router import router as analytics_router
from app.domains.auth.router import router as auth_router
from app.domains.customers.router import router as customers_router
from app.domains.dashboard.router import router as dashboard_router
from app.domains.inventory.router import router as inventory_router
from app.domains.invoices.router import router as invoice_router
from app.domains.orders.router import router as orders_router
from app.domains.payments.router import router as payments_router
from app.domains.production.router import router as production_router
from app.domains.tasks.router import router as tasks_router
from app.domains.users.credential_router import router as credential_router
from app.domains.users.router import router as users_router
from app.middleware.activity import ActivityMiddleware

# 1. Move the app instance outside of any function
app = FastAPI(title="PrintFlow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://chaydonfronted.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ActivityMiddleware)


app.include_router(auth_router)
app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(production_router)
app.include_router(tasks_router)
app.include_router(dashboard_router)
app.include_router(invoice_router)
app.include_router(
    payments_router,
)
app.include_router(inventory_router)
app.include_router(users_router)
app.include_router(credential_router)
app.include_router(analytics_router)


@app.get("/")
async def root():
    return {"message": "PrintFlow API is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# 2. (Optional) Keep the main function only if you want to run it via 'python filename.py'
def main():
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
