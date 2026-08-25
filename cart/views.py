from decimal import Decimal

import stripe
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import CustomerProfile
from products.models import ProductVariant

from .models import Cart, CartItem


def get_customer_cart(user):
    customer = user.customer_profiles.order_by("id").first()
    if customer is None:
        customer = CustomerProfile.objects.create(user=user)
    cart, _ = Cart.objects.get_or_create(customer=customer)
    return cart


@login_required
def cart_detail(request):
    cart = get_customer_cart(request.user)
    items = cart.items.select_related("variant__product").prefetch_related(
        "variant__product__images"
    )
    total = sum((item.subtotal for item in items), Decimal("0.00"))

    return render(
        request,
        "cart/detail.html",
        {
            "cart": cart,
            "items": items,
            "cart_total": total,
        },
    )


@login_required
def add_to_cart(request):
    if request.method != "POST":
        return redirect("products:home")

    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        pk=request.POST.get("variant_id"),
    )

    if variant.stock < 1:
        messages.error(request, "This product is currently out of stock.")
        return redirect("products:detail", slug=variant.product.slug)

    try:
        requested_quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        requested_quantity = 1

    quantity = max(1, requested_quantity)
    cart = get_customer_cart(request.user)
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={"quantity": min(quantity, variant.stock)},
    )

    if not created:
        item.quantity = min(item.quantity + quantity, variant.stock)
        item.save(update_fields=("quantity",))

    if quantity > variant.stock or item.quantity == variant.stock:
        messages.warning(request, f"Only {variant.stock} item(s) are available.")
    else:
        messages.success(request, f"{variant.product.product_name} added to your cart.")

    return redirect("cart:detail")


@login_required
def remove_from_cart(request, item_id):
    if request.method != "POST":
        return redirect("cart:detail")

    cart = get_customer_cart(request.user)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    product_name = item.variant.product.product_name
    item.delete()
    messages.success(request, f"{product_name} was removed from your cart.")
    return redirect("cart:detail")


@login_required
@require_POST
def create_checkout_session(request):
    cart = get_customer_cart(request.user)
    items = list(
        cart.items.select_related("variant__product")
    )

    if not items:
        messages.info(request, "Your cart is empty.")
        return redirect("cart:detail")

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Checkout is not configured yet. Please try again later.")
        return redirect("cart:detail")

    line_items = []
    for item in items:
        product = item.variant.product
        if not product.stripe_price_id:
            messages.error(
                request,
                f"{product.product_name} is not available for online checkout yet.",
            )
            return redirect("cart:detail")

        if item.quantity > item.variant.stock:
            messages.error(
                request,
                f"Only {item.variant.stock} item(s) of {product.product_name} are available.",
            )
            return redirect("cart:detail")

        line_items.append(
            {
                "price": product.stripe_price_id,
                "quantity": item.quantity,
            }
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=request.build_absolute_uri(
                reverse("cart:checkout_success")
            )
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse("cart:detail")),
            client_reference_id=str(cart.pk),
        )
    except stripe.StripeError:
        messages.error(
            request,
            "We could not start checkout. Please try again in a moment.",
        )
        return redirect("cart:detail")

    return redirect(session.url)


@login_required
def checkout_success(request):
    return render(request, "cart/success.html")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Acknowledge Stripe webhook requests until event handling is configured."""
    return JsonResponse({"received": True})
