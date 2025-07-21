from fastapi import FastAPI, HTTPException, Query, Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
import os
from bson import ObjectId

app = FastAPI()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client["Ecommerce_Data"]

# Model

class SizeModel(BaseModel):
    size: str
    quantity: int

class ProductModel(BaseModel):
    name: str
    price: float
    sizes: List[SizeModel]

class OrderItemModel(BaseModel):
    productId: str
    qty: int

class CreateOrderModel(BaseModel):
    userId: str
    items: List[OrderItemModel]

# API Endpoints

@app.post("/products")
async def create_product(product: ProductModel):
    product_dict = product.dict()
    result = await db.products.insert_one(product_dict)
    return {"id": str(result.inserted_id)}

@app.get("/products")
async def list_products(
    name: str = Query(None,description="Filter by product name (partial match)"),
    size: str = Query(None,description="Filter by product size"),
    limit: int = Query(10, gt=0,description="Number of products to return"),
    offset: int = Query(0, ge=0,description="Number of products to skip")
):
    query = {}
    if name:
        query["name"] = {"$regex": name, "$options": "i"}
    if size:
        query["sizes.size"] = size
    cursor = db.products.find(query, {"sizes": 0})
    total = await db.products.count_documents(query)
    products = []
    async for doc in cursor.skip(offset).limit(limit):
        products.append({
            "id": str(doc["_id"]),
            "name": doc["name"],
            "price": doc["price"]
        })
    page = {
        "next": offset + limit if (offset + limit) < total else None,
        "limit": limit,
        "previous": offset - limit if (offset - limit) >= 0 else None
    }   
    return {"data": products, "page": page}


@app.post("/orders", status_code=201)
async def create_order(order: CreateOrderModel):
    # Calculating total
    total = 0.0
    items_with_details = []
    for item in order.items:
        product = await db.products.find_one({"_id": ObjectId(item.productId)})
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.productId} not found")
        total += product["price"] * item.qty
        items_with_details.append({
            "productId": item.productId,
            "qty": item.qty
        })
    order_doc = {
        "userId": order.userId,
        "items": items_with_details,
        "total": total
    }
    result = await db.orders.insert_one(order_doc)
    return {"id": str(result.inserted_id)}

@app.get("/orders/{user_id}")
async def list_orders(
    user_id: str = Path(...),
    limit: int = Query(10, gt=0,description="Number of orders to return"),
    offset: int = Query(0, ge=0,description="Number of orders to skip")
):
    query = {"userId": user_id}
    cursor = db.orders.find(query)
    total_orders = await db.orders.count_documents(query)
    orders = []
    async for doc in cursor.skip(offset).limit(limit):
        items = []
        for item in doc["items"]:
            product = await db.products.find_one({"_id": ObjectId(item["productId"])})
            product_details = {"name": product["name"], "id": str(product["_id"])} if product else {}
            items.append({
                "productDetails": product_details,
                "qty": item["qty"]
            })
        orders.append({
            "id": str(doc["_id"]),
            "items": items,
            "total": doc["total"]
        })
    page = {
        "next": offset + limit if (offset + limit) < total_orders else None,
        "limit": limit,
        "previous": offset - limit if (offset - limit) >= 0 else None
    }
    return {"data": orders, "page": page} 

@app.get("/")
async def root():
    return {"message": "Ecommerce Backend API is Working"}
