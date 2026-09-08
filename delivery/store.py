from copy import deepcopy

from delivery.models import DeliveryRecord


class DeliveryStore:
    def __init__(self):
        self._records = {}
        self._idempotency = {}
        self._next_id = 1

    def create(self, payload, idempotency_key=None):
        if idempotency_key and idempotency_key in self._idempotency:
            previous = self._idempotency[idempotency_key]
            return self._records[previous], previous

        delivery_id = f"DEL-{self._next_id:04d}"
        self._next_id += 1
        record = DeliveryRecord(
            delivery_id=delivery_id,
            order_id=payload["order_id"],
            student_id=payload["student_id"],
            pickup_location=payload["pickup_location"],
            dropoff_location=payload["dropoff_location"],
            status="assigned",
            payment_verified=payload.get("payment_verified", False),
            created_by="student",
            idempotency_key=idempotency_key,
        )
        self._records[delivery_id] = record
        if idempotency_key:
            self._idempotency[idempotency_key] = delivery_id
        return record, delivery_id

    def get(self, delivery_id):
        record = self._records.get(delivery_id)
        if record is None:
            return None
        return record

    def list(self, order_id=None):
        values = list(self._records.values())
        if order_id is not None:
            values = [v for v in values if v.order_id == order_id]
        return values

    def update_status(self, delivery_id, new_status):
        record = self._records.get(delivery_id)
        if record is None:
            return None
        current = record.status
        if current == "delivered" and new_status != "delivered":
            raise ValueError("state conflict")
        if current == "assigned" and new_status == "delivered":
            record.status = new_status
            return record
        if current == "assigned" and new_status == "picked_up":
            record.status = new_status
            return record
        if current == "picked_up" and new_status == "delivered":
            record.status = new_status
            return record
        raise ValueError("state conflict")


store = DeliveryStore()
