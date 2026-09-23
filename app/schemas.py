from pydantic import BaseModel
from typing import Optional

class ArticuloBase(BaseModel):
    titulo: str
    categoria: str
    precio: str
    descripcion: Optional[str] = None
    imagen: Optional[str] = None
    activo: Optional[bool] = True

class ArticuloCrear(ArticuloBase):
    pass

class ArticuloResponse(ArticuloBase):
    id: int

    class Config:
        from_attributes = True