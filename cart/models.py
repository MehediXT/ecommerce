from django.db import models


class Cart(models.Model):
    customer = models.OneToOneField(
        "accounts.CustomerProfile",
        on_delete=models.CASCADE,
        related_name="cart",
    )

    class Meta:
        verbose_name = "cart"
        verbose_name_plural = "carts"

    def __str__(self):
        return f"Cart for {self.customer}"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("cart", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("cart", "variant"),
                name="unique_cart_variant",
            )
        ]

    def __str__(self):
        return f"{self.quantity} x {self.variant}"

    @property
    def subtotal(self):
        return self.variant.product.price * self.quantity
