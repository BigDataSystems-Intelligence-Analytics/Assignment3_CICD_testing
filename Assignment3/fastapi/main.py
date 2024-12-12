from fastapi import FastAPI
from routers import router

app = FastAPI()

#Include the routers
app.include_router(router)