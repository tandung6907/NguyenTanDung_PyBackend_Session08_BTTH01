from datetime import date
from enum import Enum
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="Logistics Carrier & Shipment Management API")


class CarrierStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class Shift(str, Enum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    NIGHT = "NIGHT"


class CarrierCreate(BaseModel):
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=3)
    max_weight_capacity: int = Field(..., gt=0)
    status: CarrierStatus


class CarrierUpdate(BaseModel):
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=3)
    max_weight_capacity: int = Field(..., gt=0)
    status: CarrierStatus


class Carrier(CarrierCreate):
    id: int


class ShipmentCreate(BaseModel):
    carrier_id: int
    order_reference: str = Field(..., min_length=1)
    total_weight: int = Field(..., gt=0)
    dispatch_date: date
    shift: Shift


class Shipment(ShipmentCreate):
    id: int


carriers: list[Carrier] = [
    Carrier(id=1, code="GHN", name="Giao Hang Nhanh", max_weight_capacity=5000, status=CarrierStatus.ACTIVE),
    Carrier(id=2, code="GHTK", name="Giao Hang Tiet Kiem", max_weight_capacity=3000, status=CarrierStatus.ACTIVE),
    Carrier(id=3, code="VTP", name="Viettel Post", max_weight_capacity=10000, status=CarrierStatus.SUSPENDED),
]

shipments: list[Shipment] = [
    Shipment(
        id=1,
        carrier_id=1,
        order_reference="ORD-2026-001",
        total_weight=4200,
        dispatch_date=date(2026, 7, 1),
        shift=Shift.MORNING,
    )
]

next_carrier_id = 4
next_shipment_id = 2


def find_carrier(carrier_id: int) -> Optional[Carrier]:
    return next((c for c in carriers if c.id == carrier_id), None)


def get_carrier_or_404(carrier_id: int) -> Carrier:
    carrier = find_carrier(carrier_id)
    if carrier is None:
        raise HTTPException(status_code=404, detail="Carrier not found")
    return carrier


def is_code_duplicate(code: str, exclude_id: Optional[int] = None) -> bool:
    return any(
        c.code.lower() == code.lower() and c.id != exclude_id
        for c in carriers
    )


@app.post("/carriers", response_model=Carrier, status_code=201)
def create_carrier(payload: CarrierCreate):
    global next_carrier_id
    if is_code_duplicate(payload.code):
        raise HTTPException(status_code=400, detail="Carrier code already exists")

    carrier = Carrier(id=next_carrier_id, **payload.model_dump())
    carriers.append(carrier)
    next_carrier_id += 1
    return carrier


@app.get("/carriers", response_model=list[Carrier])
def list_carriers(
    keyword: Optional[str] = Query(default=None),
    status: Optional[CarrierStatus] = Query(default=None),
    min_weight: Optional[int] = Query(default=None, gt=0),
):
    result = carriers

    if keyword:
        keyword_lower = keyword.lower()
        result = [
            c for c in result
            if keyword_lower in c.code.lower() or keyword_lower in c.name.lower()
        ]

    if status:
        result = [c for c in result if c.status == status]

    if min_weight is not None:
        result = [c for c in result if c.max_weight_capacity >= min_weight]

    return result


@app.get("/carriers/{carrier_id}", response_model=Carrier)
def get_carrier(carrier_id: int):
    return get_carrier_or_404(carrier_id)


@app.put("/carriers/{carrier_id}", response_model=Carrier)
def update_carrier(carrier_id: int, payload: CarrierUpdate):
    carrier = get_carrier_or_404(carrier_id)

    if is_code_duplicate(payload.code, exclude_id=carrier_id):
        raise HTTPException(status_code=400, detail="Carrier code already exists")

    carrier.code = payload.code
    carrier.name = payload.name
    carrier.max_weight_capacity = payload.max_weight_capacity
    carrier.status = payload.status
    return carrier


@app.delete("/carriers/{carrier_id}", status_code=204)
def delete_carrier(carrier_id: int):
    carrier = get_carrier_or_404(carrier_id)
    carriers.remove(carrier)
    return None


@app.post("/shipments", response_model=Shipment, status_code=201)
def create_shipment(payload: ShipmentCreate):
    global next_shipment_id

    carrier = find_carrier(payload.carrier_id)
    if carrier is None:
        raise HTTPException(status_code=404, detail="Carrier not found")

    if carrier.status != CarrierStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Carrier is not active")

    if payload.total_weight > carrier.max_weight_capacity:
        raise HTTPException(status_code=400, detail="Total weight exceeds carrier max weight capacity")

    schedule_conflict = any(
        s.carrier_id == payload.carrier_id
        and s.dispatch_date == payload.dispatch_date
        and s.shift == payload.shift
        for s in shipments
    )
    if schedule_conflict:
        raise HTTPException(status_code=409, detail="Carrier already has a shipment scheduled for this date and shift")

    shipment = Shipment(id=next_shipment_id, **payload.model_dump())
    shipments.append(shipment)
    next_shipment_id += 1
    return shipment


@app.get("/shipments", response_model=list[Shipment])
def list_shipments():
    return shipments