import os
import shutil
import secrets
import zipfile
import tempfile
from typing import List, Optional

from fastapi import FastAPI, Depends, Request, HTTPException, status, File, UploadFile, Form
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import engine, get_db

# Crear tablas en SQLite si no existen
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Catálogo con FastAPI y SQLite")

# Obtener la ruta exacta absoluta del archivo SQLite usado por SQLAlchemy
def obtener_ruta_db_absoluta() -> str:
    db_file = engine.url.database
    if not db_file:
        return os.path.abspath("sql_app.db")
    return os.path.abspath(db_file)

# Sembrar categorías iniciales en la base de datos si está vacía
def inicializar_categorias():
    db = next(get_db())
    if db.query(models.Categoria).count() == 0:
        categorias_base = ["Tecnología", "Indumentaria", "Hogar", "Calzado", "Accesorios", "Otros"]
        for cat_nombre in categorias_base:
            db.add(models.Categoria(nombre=cat_nombre))
        db.commit()

inicializar_categorias()

# Carpeta para archivos estáticos subidos desde la PC
UPLOAD_DIR = "app/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Montar ruta de archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# ---------------------------------------------------------
# SEGURIDAD Y AUTENTICACIÓN (HTTP BASIC AUTH)
# ---------------------------------------------------------
security = HTTPBasic()
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "TuClaveSegura123")

def verificar_admin(credentials: HTTPBasicCredentials = Depends(security)):
    usuario_correcto = secrets.compare_digest(credentials.username, ADMIN_USER)
    clave_correcta = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    
    if not (usuario_correcto and clave_correcta):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ---------------------------------------------------------
# RUTAS DE VISTAS (HTML)
# ---------------------------------------------------------
@app.get("/")
def vista_catalogo(request: Request, db: Session = Depends(get_db)):
    articulos = db.query(models.Articulo).filter(models.Articulo.activo == True).all()
    categorias = [c.nombre for c in db.query(models.Categoria).all()]
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={
            "articulos": articulos,
            "categorias": categorias
        }
    )

@app.get("/admin")
def vista_admin(
    request: Request, 
    db: Session = Depends(get_db), 
    _user: str = Depends(verificar_admin)
):
    articulos = db.query(models.Articulo).all()
    categorias_obj = db.query(models.Categoria).all()
    categorias_nombres = [c.nombre for c in categorias_obj]
    return templates.TemplateResponse(
        request=request, 
        name="admin.html", 
        context={
            "articulos": articulos,
            "categorias": categorias_nombres,
            "categorias_obj": categorias_obj
        }
    )

# ---------------------------------------------------------
# RUTAS DE BACKUP Y RESTAURACIÓN
# ---------------------------------------------------------
@app.get("/admin/descargar-db")
def descargar_base_de_datos(_user: str = Depends(verificar_admin)):
    db_path = obtener_ruta_db_absoluta()
    
    if not os.path.exists(db_path):
        raise HTTPException(
            status_code=404, 
            detail=f"Archivo de base de datos no encontrado en la ruta: {db_path}"
        )
    
    return FileResponse(
        path=db_path, 
        filename="backup_catalogo.db", 
        media_type="application/x-sqlite3"
    )

@app.post("/admin/restaurar-db")
def restaurar_base_de_datos(
    archivo_db: UploadFile = File(...),
    _user: str = Depends(verificar_admin)
):
    if not archivo_db.filename.endswith(('.db', '.sqlite', '.sqlite3')):
        raise HTTPException(status_code=400, detail="El archivo subido no parece ser una base de datos SQLite válida.")

    db_path = obtener_ruta_db_absoluta()
    
    # Cerrar conexiones activas de la BD para permitir sobreescribir el archivo sin bloqueos
    engine.dispose()
    
    with open(db_path, "wb") as buffer:
        shutil.copyfileobj(archivo_db.file, buffer)
        
    return {"ok": True, "message": "Base de datos restaurada correctamente"}

@app.get("/admin/descargar-zip")
def descargar_backup_completo_zip(_user: str = Depends(verificar_admin)):
    temp_dir = tempfile.gettempdir()
    zip_path = os.path.join(temp_dir, "backup_completo_proyecto.zip")
    base_dir = os.getcwd()
    
    excluir = {'.venv', 'venv', '.git', '__pycache__', '.pytest_cache'}

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in excluir]
            for file in files:
                if file.endswith(('.zip', '.pyc', '.db-journal')):
                    continue
                archivo_completo = os.path.join(root, file)
                ruta_relativa = os.path.relpath(archivo_completo, base_dir)
                zipf.write(archivo_completo, ruta_relativa)

    return FileResponse(
        path=zip_path, 
        filename="backup_completo_proyecto.zip", 
        media_type="application/zip"
    )

# ---------------------------------------------------------
# RUTAS DE API (CATEGORÍAS)
# ---------------------------------------------------------
@app.post("/api/categorias", status_code=status.HTTP_201_CREATED)
def crear_categoria(
    nombre: str = Form(...),
    db: Session = Depends(get_db),
    _user: str = Depends(verificar_admin)
):
    nombre_limpio = nombre.strip().capitalize()
    existe = db.query(models.Categoria).filter(models.Categoria.nombre == nombre_limpio).first()
    if existe:
        raise HTTPException(status_code=400, detail="La categoría ya existe")
    
    nueva_cat = models.Categoria(nombre=nombre_limpio)
    db.add(nueva_cat)
    db.commit()
    db.refresh(nueva_cat)
    return {"id": nueva_cat.id, "nombre": nueva_cat.nombre}

@app.delete("/api/categorias/{categoria_id}")
def eliminar_categoria(
    categoria_id: int,
    db: Session = Depends(get_db),
    _user: str = Depends(verificar_admin)
):
    cat = db.query(models.Categoria).filter(models.Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    cantidad_productos = db.query(models.Articulo).filter(models.Articulo.categoria == cat.nombre).count()
    if cantidad_productos > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar: Hay {cantidad_productos} producto(s) asignado(s) a la categoría '{cat.nombre}'."
        )

    db.delete(cat)
    db.commit()
    return {"ok": True, "message": "Categoría eliminada"}

# ---------------------------------------------------------
# RUTAS DE API (ARTÍCULOS)
# ---------------------------------------------------------
@app.get("/api/articulos", response_model=List[schemas.ArticuloResponse])
def listar_articulos(db: Session = Depends(get_db)):
    return db.query(models.Articulo).filter(models.Articulo.activo == True).all()

@app.post("/api/articulos", response_model=schemas.ArticuloResponse, status_code=status.HTTP_201_CREATED)
def crear_articulo(
    titulo: str = Form(...),
    categoria: str = Form(...),
    precio: str = Form(...),
    moneda: str = Form("ARS"),
    descripcion: Optional[str] = Form(None),
    imagen_url: Optional[str] = Form(None),
    imagen_archivo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _user: str = Depends(verificar_admin)
):
    ruta_imagen = imagen_url

    if imagen_archivo and imagen_archivo.filename:
        extension = os.path.splitext(imagen_archivo.filename)[1]
        nombre_guardado = f"{secrets.token_hex(8)}{extension}"
        filepath = os.path.join(UPLOAD_DIR, nombre_guardado)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(imagen_archivo.file, buffer)
            
        ruta_imagen = f"/static/uploads/{nombre_guardado}"

    simbolo = "US$" if moneda == "USD" else "$"
    precio_limpio = precio.replace("$", "").replace("US", "").strip()
    precio_formateado = f"{simbolo} {precio_limpio}"

    nuevo_articulo = models.Articulo(
        titulo=titulo,
        categoria=categoria,
        precio=precio_formateado,
        descripcion=descripcion,
        imagen=ruta_imagen,
        activo=True
    )
    db.add(nuevo_articulo)
    db.commit()
    db.refresh(nuevo_articulo)
    return nuevo_articulo

@app.put("/api/articulos/{articulo_id}", response_model=schemas.ArticuloResponse)
def actualizar_articulo(
    articulo_id: int,
    titulo: str = Form(...),
    categoria: str = Form(...),
    precio: str = Form(...),
    moneda: str = Form("ARS"),
    descripcion: Optional[str] = Form(None),
    imagen_url: Optional[str] = Form(None),
    imagen_archivo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    _user: str = Depends(verificar_admin)
):
    articulo = db.query(models.Articulo).filter(models.Articulo.id == articulo_id).first()
    if not articulo:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    
    ruta_imagen = imagen_url if imagen_url else articulo.imagen

    if imagen_archivo and imagen_archivo.filename:
        extension = os.path.splitext(imagen_archivo.filename)[1]
        nombre_guardado = f"{secrets.token_hex(8)}{extension}"
        filepath = os.path.join(UPLOAD_DIR, nombre_guardado)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(imagen_archivo.file, buffer)
            
        ruta_imagen = f"/static/uploads/{nombre_guardado}"

    simbolo = "US$" if moneda == "USD" else "$"
    precio_limpio = precio.replace("$", "").replace("US", "").strip()
    precio_formateado = f"{simbolo} {precio_limpio}"

    articulo.titulo = titulo
    articulo.categoria = categoria
    articulo.precio = precio_formateado
    articulo.descripcion = descripcion
    articulo.imagen = ruta_imagen

    db.commit()
    db.refresh(articulo)
    return articulo

@app.delete("/api/articulos/{articulo_id}")
def eliminar_articulo(
    articulo_id: int, 
    db: Session = Depends(get_db),
    _user: str = Depends(verificar_admin)
):
    articulo = db.query(models.Articulo).filter(models.Articulo.id == articulo_id).first()
    if not articulo:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    db.delete(articulo)
    db.commit()
    return {"ok": True, "message": "Artículo eliminado"}