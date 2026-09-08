import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import Address, CustomerProfile
from products.models import Product

from .models import Order, OrderItem


def money_from_minor(amount, currency):
    # Stripe represents ISK and UGX with two decimal places for compatibility.
    zero_decimal = {"bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf", "vnd", "vuv", "xaf", "xof", "xpf"}
    exponent = 0 if currency in zero_decimal else 3 if currency in {"bhd", "jod", "kwd", "omr", "tnd"} else 2
    return Decimal(amount) / (10 ** exponent)


def checkout_metadata(items, email, user_id=None):
    if not email:
        raise ValueError("An account email is required for checkout.")
    # Each Stripe metadata value is limited to 500 characters; reserve keys for
    # the account email, schema marker, and item count.
    if not 1 <= len(items) <= 40:
        raise ValueError("Please check out with at most 40 cart items at a time.")
    return {
        "order_schema": "2" if user_id is not None else "1",
        **({"user_id": str(user_id)} if user_id is not None else {}),
        "user_email": email,
        "item_count": str(len(items)),
        **{f"item_{i}": json.dumps(item, separators=(",", ":")) for i, item in enumerate(items)},
    }


def create_paid_order_from_checkout_session(session):
    """Create an order from a verified, paid Checkout Session.

    Checkout stores the collected address on ``shipping_details`` while the
    existing order builder consumes a PaymentIntent.  Normalize the session
    here so both the success redirect and the webhook use the same idempotent
    order creation code.
    """
    if not isinstance(session, dict) or session.get("payment_status") != "paid":
        raise ValueError("Checkout Session is not paid.")

    payment_intent = session.get("payment_intent")
    if not isinstance(payment_intent, dict):
        raise ValueError("Checkout Session is missing its PaymentIntent.")

    intent = dict(payment_intent)
    shipping = session.get("shipping_details") or intent.get("shipping")
    if shipping is not None:
        intent["shipping"] = shipping

    customer_details = session.get("customer_details") or {}
    if not intent.get("receipt_email"):
        intent["receipt_email"] = (
            customer_details.get("email")
            if isinstance(customer_details, dict)
            else None
        ) or session.get("customer_email")

    return create_paid_order(intent)


@transaction.atomic
def create_paid_order(intent):
    if not isinstance(intent, dict) or not isinstance(intent.get("id"), str) or not intent["id"]:
        raise ValueError("Missing payment identifier.")
    existing = Order.objects.filter(stripe_payment_intent_id=intent["id"]).first()
    if existing:
        return existing
    metadata = intent.get("metadata") or {}
    if not isinstance(metadata, dict) or metadata.get("order_schema") not in {"1", "2"}:
        raise ValueError("Unsupported order metadata schema.")
    email = metadata.get("user_email") or intent.get("receipt_email")
    if not email or intent.get("status") != "succeeded":
        raise ValueError("Payment must be successful and contain a user email.")
    # Lock the account to serialize simultaneous deliveries, including the first
    # payment where the customer profile might not exist yet.
    users = get_user_model().objects.select_for_update()
    if metadata["order_schema"] == "2":
        user = users.get(pk=metadata["user_id"])
    else:
        user = users.get(email__iexact=email)
    existing = Order.objects.filter(stripe_payment_intent_id=intent["id"]).first()
    if existing:
        return existing
    customer = user.customer_profiles.order_by("id").first()
    if customer is None:
        customer = CustomerProfile.objects.create(user=user)

    count = int(metadata["item_count"])
    if not 1 <= count <= 40:
        raise ValueError("Invalid purchased item count.")
    currency = intent["currency"]
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise ValueError("Invalid payment currency.")
    currency = currency.lower()
    if type(intent["amount_received"]) is not int or intent["amount_received"] < 0:
        raise ValueError("Invalid paid amount.")
    items = []
    total_minor = 0
    for index in range(count):
        product_id, quantity, unit_amount = json.loads(metadata[f"item_{index}"])
        if any(type(value) is not int for value in (product_id, quantity, unit_amount)) or quantity <= 0 or unit_amount < 0:
            raise ValueError("Invalid purchased item.")
        items.append(OrderItem(
            product=Product.objects.get(pk=product_id),
            price=money_from_minor(unit_amount, currency), quantity=quantity,
        ))
        total_minor += unit_amount * quantity
    if total_minor != intent["amount_received"]:
        raise ValueError("Purchased items do not match the paid amount.")

    shipping = intent.get("shipping") or {}
    if not isinstance(shipping, dict):
        raise ValueError("Invalid shipping details.")
    address_data = shipping.get("address") or {}
    if not isinstance(address_data, dict):
        raise ValueError("Invalid shipping address.")
    if not address_data.get("country") or not address_data.get("line1"):
        raise ValueError("The payment is missing its shipping address.")
    address = Address(
        country=address_data["country"], city=address_data.get("city") or "",
        postal_code=address_data.get("postal_code") or "",
        street_address_line=" ".join(filter(None, (address_data["line1"], address_data.get("line2")))),
    )
    address.full_clean(exclude=[field for field in ("city", "postal_code") if not getattr(address, field)])
    address.save()
    order = Order(
        customer=customer, address=address, status=Order.Status.PAID,
        total_amount=money_from_minor(intent["amount_received"], currency),
        currency=currency, stripe_payment_intent_id=intent["id"],
    )
    order.full_clean()
    order.save()
    for item in items:
        item.order = order
        item.full_clean()
    OrderItem.objects.bulk_create(items)
    return order
