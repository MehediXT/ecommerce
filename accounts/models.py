from django.conf import settings
from django.db import models


class Address(models.Model):
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    street_address_line = models.CharField(max_length=255)

    class Meta:
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.street_address_line}, {self.city}, {self.country}"


class CustomerProfile(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profiles",
    )
    phone = models.CharField(max_length=30, blank=True)
    profile_image = models.ImageField(
        upload_to="customer_profiles/",
        blank=True,
        null=True,
    )
    addresses = models.ManyToManyField(
        Address,
        related_name="customer_profiles",
        blank=True,
    )

    def __str__(self):
        return f"Customer profile for {self.user}"
