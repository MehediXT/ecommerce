from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "status", "total_amount", "currency", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("stripe_payment_intent_id", "customer__user__email")
    readonly_fields = ("stripe_payment_intent_id", "created_at")
    inlines = (OrderItemInline,)
