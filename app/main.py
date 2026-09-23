from fastapi import FastAPI, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlalchemy.orm
# (Importá acá tus modelos y la base de datos según los tengas configurados en tu proyecto)

app = FastAPI()

# 1. Montar la carpeta estática para CSS, JS e imágenes/audios
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 2. Configurar las plantillas HTML
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def leer_inicio(request: Request):
    # Acá pasás los datos que necesites a tu plantilla index.html
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/admin/restaurar-db")
def restaurar_base_de_datos(file: UploadFile = File(...)):
    # Tu lógica actual para restaurar la base de datos con python-multipart
    return {"mensaje": "Base restaurada con éxito"}