from django.db import models


class ProductCategory(models.Model):
    category_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    class Meta:
        verbose_name = "product category"
        verbose_name_plural = "product categories"
        ordering = ("category_name",)

    def __str__(self):
        return self.category_name


class Product(models.Model):
    product_name = models.CharField(max_length=255)
    product_category = models.ForeignKey(
        ProductCategory,
        on_delete=models.CASCADE,
        related_name="products",
    )
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_product_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_price_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ("product_name",)

    def __str__(self):
        return self.product_name


class ProductImage(models.Model):
    image = models.ImageField(upload_to="products/images/")
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )

    def __str__(self):
        return f"Image for {self.product}"


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    image = models.ImageField(upload_to="products/variants/")
    color = models.CharField(max_length=100)
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("product", "color")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "color"),
                name="unique_product_variant_color",
            )
        ]

    def __str__(self):
        return f"{self.product} - {self.color}"
