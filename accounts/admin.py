from django.contrib import admin

from .models import Address, CustomerProfile


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("street_address_line", "city", "country", "postal_code")
    search_fields = ("street_address_line", "city", "country", "postal_code")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
    search_fields = ("user__username", "user__email", "phone")
    filter_horizontal = ("addresses",)
