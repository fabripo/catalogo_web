from sqlalchemy import Column, Integer, String, Boolean, Text
from app.database import Base

class Articulo(Base):
    __tablename__ = "articulos"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    categoria = Column(String, nullable=False)
    precio = Column(String, nullable=False)
    descripcion = Column(Text, nullable=True)
    imagen = Column(String, nullable=True)
    activo = Column(Boolean, default=True)

class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, nullable=False)