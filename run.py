import uvicorn
import os
import sys

if __name__ == "__main__":
    print("==================================================")
    print("       🚀 TOLK — MVP Platform Starting")
    print("       URL: http://127.0.0.1:8000")
    print("==================================================")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
