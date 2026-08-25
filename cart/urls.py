from django.urls import path

from . import views


app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("add/", views.add_to_cart, name="add"),
    path("remove/<int:item_id>/", views.remove_from_cart, name="remove"),
    path("checkout/", views.create_checkout_session, name="checkout"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("webhook/", views.stripe_webhook, name="stripe_webhook"),
]
