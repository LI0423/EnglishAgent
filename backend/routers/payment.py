from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from uuid import uuid4
import hashlib
import os
import time

from ..deps import get_current_user
from ..db import (
    create_payment_order,
    get_payment_order,
    list_user_payment_orders,
    update_payment_order_status,
    create_payment_transaction,
    upsert_user_entitlement,
    list_user_entitlements,
)

router = APIRouter()

MOCK_SECRET = os.environ.get("PAYMENT_MOCK_SECRET", "mock-secret")

PRODUCTS: Dict[str, Dict[str, Any]] = {
    "writing_ai_review_pack_10": {
        "code": "writing_ai_review_pack_10",
        "name": "写作AI批改 10次包",
        "price_cents": 1500,
        "currency": "CNY",
        "entitlements": {"writing_ai_review": 10},
    },
    "writing_ai_review_pack_30": {
        "code": "writing_ai_review_pack_30",
        "name": "写作AI批改 30次包",
        "price_cents": 3900,
        "currency": "CNY",
        "entitlements": {"writing_ai_review": 30},
    },
}


def _mock_sign(order_id: str, status: str, provider_txn_id: str) -> str:
    raw = f"{order_id}|{status}|{provider_txn_id}|{MOCK_SECRET}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ProductItem(BaseModel):
    code: str
    name: str
    price_cents: int
    currency: str
    entitlements: Dict[str, int]


class CreateOrderRequest(BaseModel):
    product_code: str
    quantity: int = Field(1, ge=1, le=10)


class OrderItem(BaseModel):
    id: str
    user_id: str
    product_code: str
    product_name: str
    quantity: int
    unit_price_cents: int
    total_price_cents: int
    currency: str
    status: str
    created_at: int
    updated_at: int
    paid_at: int | None = None


class CreateOrderResponse(BaseModel):
    order: OrderItem


class MockPayResponse(BaseModel):
    order_id: str
    provider: str
    provider_txn_id: str
    amount_cents: int
    callback_payload: Dict[str, Any]
    callback_signature: str
    message: str


class MockCallbackRequest(BaseModel):
    order_id: str
    provider_txn_id: str
    status: str = "success"
    signature: str
    raw_payload: Dict[str, Any] = {}


@router.get("/payment/products", response_model=List[ProductItem], tags=["payment"])
async def list_products(current_user: dict = Depends(get_current_user)):
    return [
        ProductItem(
            code=str(x["code"]),
            name=str(x["name"]),
            price_cents=int(x["price_cents"]),
            currency=str(x["currency"]),
            entitlements={k: int(v) for k, v in (x.get("entitlements") or {}).items()},
        )
        for x in PRODUCTS.values()
    ]


@router.post("/payment/order", response_model=CreateOrderResponse, tags=["payment"])
async def create_order(req: CreateOrderRequest, current_user: dict = Depends(get_current_user)):
    product = PRODUCTS.get(str(req.product_code or ""))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    qty = max(1, int(req.quantity))
    order_id = str(uuid4())
    create_payment_order(
        order_id,
        user_id=str(current_user["id"]),
        product_code=str(product["code"]),
        product_name=str(product["name"]),
        quantity=qty,
        unit_price_cents=int(product["price_cents"]),
        total_price_cents=int(product["price_cents"]) * qty,
        currency=str(product["currency"]),
        metadata={"product_snapshot": product, "quantity": qty},
    )
    row = get_payment_order(order_id)
    return CreateOrderResponse(
        order=OrderItem(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            product_code=str(row.get("product_code") or ""),
            product_name=str(row.get("product_name") or ""),
            quantity=int(row.get("quantity") or 1),
            unit_price_cents=int(row.get("unit_price_cents") or 0),
            total_price_cents=int(row.get("total_price_cents") or 0),
            currency=str(row.get("currency") or "CNY"),
            status=str(row.get("status") or "pending"),
            created_at=int(row.get("created_at") or 0),
            updated_at=int(row.get("updated_at") or 0),
            paid_at=int(row.get("paid_at")) if row.get("paid_at") else None,
        )
    )


@router.get("/payment/orders", response_model=List[OrderItem], tags=["payment"])
async def get_orders(limit: int = 30, current_user: dict = Depends(get_current_user)):
    rows = list_user_payment_orders(str(current_user["id"]), limit=max(1, min(100, int(limit))))
    return [
        OrderItem(
            id=str(x["id"]),
            user_id=str(x["user_id"]),
            product_code=str(x.get("product_code") or ""),
            product_name=str(x.get("product_name") or ""),
            quantity=int(x.get("quantity") or 1),
            unit_price_cents=int(x.get("unit_price_cents") or 0),
            total_price_cents=int(x.get("total_price_cents") or 0),
            currency=str(x.get("currency") or "CNY"),
            status=str(x.get("status") or "pending"),
            created_at=int(x.get("created_at") or 0),
            updated_at=int(x.get("updated_at") or 0),
            paid_at=int(x.get("paid_at")) if x.get("paid_at") else None,
        )
        for x in rows
    ]


@router.post("/payment/order/{order_id}/mock-pay", response_model=MockPayResponse, tags=["payment"])
async def mock_pay_order(order_id: str, current_user: dict = Depends(get_current_user)):
    row = get_payment_order(order_id)
    if not row or str(row.get("user_id")) != str(current_user["id"]):
        raise HTTPException(status_code=404, detail="Order not found")
    if str(row.get("status")) == "paid":
        raise HTTPException(status_code=400, detail="Order already paid")
    provider_txn_id = f"mock_{uuid4().hex[:18]}"
    signature = _mock_sign(order_id, "success", provider_txn_id)
    payload = {
        "order_id": order_id,
        "provider_txn_id": provider_txn_id,
        "status": "success",
        "signature": signature,
    }
    return MockPayResponse(
        order_id=order_id,
        provider="mock",
        provider_txn_id=provider_txn_id,
        amount_cents=int(row.get("total_price_cents") or 0),
        callback_payload=payload,
        callback_signature=signature,
        message="请调用 /payment/callback/mock 完成支付回调",
    )


@router.post("/payment/callback/mock", tags=["payment"])
async def mock_callback(req: MockCallbackRequest):
    row = get_payment_order(req.order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    expected_sign = _mock_sign(req.order_id, req.status, req.provider_txn_id)
    if str(req.signature) != expected_sign:
        raise HTTPException(status_code=400, detail="Invalid callback signature")

    ok_tx = create_payment_transaction(
        str(uuid4()),
        order_id=req.order_id,
        user_id=str(row["user_id"]),
        provider="mock",
        provider_txn_id=str(req.provider_txn_id),
        amount_cents=int(row.get("total_price_cents") or 0),
        status="success" if req.status == "success" else "failed",
        raw_payload=req.raw_payload or {},
    )

    if req.status != "success":
        update_payment_order_status(req.order_id, "failed")
        return {"ok": True, "order_id": req.order_id, "status": "failed", "transaction_created": ok_tx}

    if str(row.get("status")) != "paid":
        update_payment_order_status(req.order_id, "paid", paid_at=int(time.time()))
        product_code = str(row.get("product_code") or "")
        product = PRODUCTS.get(product_code) or {}
        qty = int(row.get("quantity") or 1)
        ent = product.get("entitlements") or {}
        for feature_code, base_count in ent.items():
            upsert_user_entitlement(
                user_id=str(row["user_id"]),
                feature_code=str(feature_code),
                delta=int(base_count) * qty,
                source_type="payment_order_paid",
                source_id=str(req.order_id),
                note=f"支付订单到账：{product_code}",
                metadata={"order_id": req.order_id, "product_code": product_code},
            )

    return {"ok": True, "order_id": req.order_id, "status": "paid", "transaction_created": ok_tx}


@router.get("/payment/entitlements", tags=["payment"])
async def get_entitlements(current_user: dict = Depends(get_current_user)):
    return list_user_entitlements(str(current_user["id"]))
