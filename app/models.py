from pydantic import BaseModel 

class products(BaseModel):
    product_id : int 
    name : str
    price : float 
    category : str
    unit  : int 
    is_avaliable : bool

class user(BaseModel) :
    id : int 
    name : str
    is_active  : bool
    