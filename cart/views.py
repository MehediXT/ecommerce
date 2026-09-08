from decimal import Decimal
import logging

import stripe
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import CustomerProfile
from products.models import ProductVariant
from orders.services import (
    checkout_metadata,
    create_paid_order,
    create_paid_order_from_checkout_session,
)

from .models import Cart, CartItem

logger = logging.getLogger(__name__)


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

    try:
        variant_id = int(request.POST.get("variant_id", ""))
    except (TypeError, ValueError):
        messages.error(request, "Please select a valid product variant.")
        return redirect("products:home")

    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        pk=variant_id,
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

        if item.quantity < 1 or item.quantity > item.variant.stock:
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
        purchased_items = []
        currencies = set()
        for item in items:
            price = stripe.Price.retrieve(item.variant.product.stripe_price_id).to_dict()
            if price.get("unit_amount") is None or price.get("billing_scheme") != "per_unit" or price.get("type") != "one_time":
                raise ValueError("Checkout requires a fixed, one-time product price.")
            currencies.add(price["currency"])
            purchased_items.append([item.variant.product_id, item.quantity, price["unit_amount"]])
        if len(currencies) != 1:
            raise ValueError("All checkout items must use the same currency.")
        metadata = checkout_metadata(purchased_items, request.user.email, request.user.pk)
        session = stripe.checkout.Session.create(
            mode="payment",
            adaptive_pricing={"enabled": False},
            line_items=line_items,
            success_url=request.build_absolute_uri(
                reverse("cart:checkout_success")
            )
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse("cart:detail")),
            client_reference_id=str(cart.pk),
            customer_email=request.user.email,
            payment_intent_data={"receipt_email": request.user.email, "metadata": metadata},
            shipping_address_collection={"allowed_countries": settings.STRIPE_SHIPPING_COUNTRIES},
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("cart:detail")
    except stripe.StripeError:
        messages.error(
            request,
            "We could not start checkout. Please try again in a moment.",
        )
        return redirect("cart:detail")

    return redirect(session.url)


@login_required
def checkout_success(request):
    session_id = request.GET.get("session_id", "")
    if not session_id or not settings.STRIPE_SECRET_KEY:
        messages.error(request, "We could not verify this checkout.")
        return redirect("cart:detail")
    try:
        session = stripe.checkout.Session.retrieve(
            session_id,
            api_key=settings.STRIPE_SECRET_KEY,
            expand=["payment_intent"],
        ).to_dict()
    except stripe.StripeError:
        messages.error(request, "We could not verify your payment. Please try again later.")
        return redirect("cart:detail")
    cart = get_customer_cart(request.user)
    if session.get("client_reference_id") != str(cart.pk):
        messages.error(request, "We could not verify this checkout.")
        return redirect("cart:detail")

    payment_confirmed = session.get("payment_status") == "paid"
    order_created = False
    if payment_confirmed:
        try:
            # The browser return is a verified Stripe response, so it can
            # complete the order immediately. The webhook remains idempotent
            # and can safely retry the same PaymentIntent later.
            create_paid_order_from_checkout_session(session)
            cart.items.all().delete()
            order_created = True
        except (
            ValueError,
            KeyError,
            TypeError,
            ObjectDoesNotExist,
            MultipleObjectsReturned,
            ValidationError,
        ):
            logger.exception("Could not create order for Checkout Session %s", session_id)

    return render(
        request,
        "cart/success.html",
        {
            "payment_confirmed": payment_confirmed,
            "order_created": order_created,
        },
    )


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return JsonResponse({"error": "Webhook is not configured."}, status=503)
    try:
        event = stripe.Webhook.construct_event(
            request.body, request.headers.get("Stripe-Signature", ""),
            settings.STRIPE_WEBHOOK_SECRET,
        ).to_dict()
    except (ValueError, TypeError, KeyError, AttributeError, stripe.SignatureVerificationError):
        return JsonResponse({"error": "Invalid webhook."}, status=400)

    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
        return JsonResponse({"error": "Invalid webhook."}, status=400)
    if not isinstance(event.get("data"), dict):
        return JsonResponse({"error": "Invalid webhook."}, status=400)

    if event["type"] == "payment_intent.succeeded":
        try:
            create_paid_order(event["data"]["object"])
        except (
            ValueError,
            KeyError,
            TypeError,
            ObjectDoesNotExist,
            MultipleObjectsReturned,
            ValidationError,
        ):
            logger.exception("Could not create order for Stripe event %s", event.get("id"))
            return JsonResponse({"error": "Order creation failed."}, status=422)
    elif event["type"] in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        checkout_session = event["data"].get("object", {})
        if not isinstance(checkout_session, dict):
            return JsonResponse({"error": "Invalid webhook."}, status=400)
        if checkout_session.get("payment_status") == "paid":
            try:
                # The Checkout Session contains the collected shipping address;
                # expand its PaymentIntent to reuse the same order builder.
                checkout_session = stripe.checkout.Session.retrieve(
                    checkout_session["id"],
                    api_key=settings.STRIPE_SECRET_KEY,
                    expand=["payment_intent"],
                ).to_dict()
                create_paid_order_from_checkout_session(checkout_session)
            except (
                ValueError,
                KeyError,
                TypeError,
                ObjectDoesNotExist,
                MultipleObjectsReturned,
                ValidationError,
                stripe.StripeError,
            ):
                logger.exception("Could not create order for Stripe event %s", event.get("id"))
                return JsonResponse({"error": "Order creation failed."}, status=422)
    return JsonResponse({"received": True})
