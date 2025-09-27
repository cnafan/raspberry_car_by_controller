import uvicorn

if __name__ == "__main__":
    uvicorn.run("raspberry_car_by_controller.main:app", host="0.0.0.0", port=8000, reload=True)
