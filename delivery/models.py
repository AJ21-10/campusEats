class DeliveryRecord:
    def __init__(
        self,
        delivery_id,
        order_id,
        student_id,
        pickup_location,
        dropoff_location,
        status,
        payment_verified,
        created_by,
        idempotency_key=None,
    ):
        self.delivery_id = delivery_id
        self.order_id = order_id
        self.student_id = student_id
        self.pickup_location = pickup_location
        self.dropoff_location = dropoff_location
        self.status = status
        self.payment_verified = payment_verified
        self.created_by = created_by
        self.idempotency_key = idempotency_key

    def as_json(self):
        return {
            "delivery_id": self.delivery_id,
            "order_id": self.order_id,
            "student_id": self.student_id,
            "pickup_location": self.pickup_location,
            "dropoff_location": self.dropoff_location,
            "status": self.status,
            "payment_verified": self.payment_verified,
        }
