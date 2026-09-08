from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(
        "accounts.CustomerProfile", on_delete=models.PROTECT, related_name="orders"
    )
    address = models.ForeignKey(
        "accounts.Address", on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    total_amount = models.DecimalField(max_digits=15, decimal_places=3)
    currency = models.CharField(max_length=3)
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.pk} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    price = models.DecimalField(max_digits=15, decimal_places=3)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="order_item_quantity_positive"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="order_item_price_nonnegative"),
        ]
