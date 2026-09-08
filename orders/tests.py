import hashlib
import hmac
import json
import time
import stripe
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Address, CustomerProfile
from cart.models import Cart, CartItem
from products.models import Product, ProductCategory, ProductVariant

from .models import Order, OrderItem
from .services import checkout_metadata, money_from_minor


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test", STRIPE_SECRET_KEY="sk_test")
class OrderWebhookTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="buyer", email="buyer@example.com")
        category = ProductCategory.objects.create(category_name="Clothes", slug="clothes")
        self.product = Product.objects.create(
            product_name="Shirt", slug="shirt", product_category=category,
            price="99.00", stripe_price_id="price_test",
        )
        self.intent = {
            "id": "pi_test", "object": "payment_intent", "status": "succeeded",
            "currency": "usd", "amount_received": 2500,
            "receipt_email": self.user.email,
            "metadata": checkout_metadata([[self.product.pk, 2, 1250]], self.user.email),
            "shipping": {"address": {"country": "BD", "city": "Dhaka", "postal_code": "1200", "line1": "12 Main Road", "line2": "Flat 2"}},
        }

    def deliver(self, event_type="payment_intent.succeeded", signature=True):
        body = json.dumps({"id": "evt_test", "object": "event", "type": event_type, "data": {"object": self.intent}})
        timestamp = int(time.time())
        digest = hmac.new(b"whsec_test", f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
        return self.client.post(
            reverse("cart:stripe_webhook"), data=body, content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={digest}" if signature else "invalid",
        )

    def test_paid_order_uses_event_snapshot_and_email(self):
        self.assertEqual(self.deliver().status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.customer.user, self.user)
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.total_amount, Decimal("25.00"))
        self.assertEqual(order.address.street_address_line, "12 Main Road Flat 2")
        item = order.items.get()
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.price, Decimal("12.50"))
        self.assertEqual(item.quantity, 2)

    def test_duplicate_delivery_does_not_duplicate_order_or_address(self):
        self.assertEqual(self.deliver().status_code, 200)
        Order.objects.update(status=Order.Status.SHIPPED)
        self.assertEqual(self.deliver().status_code, 200)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(Address.objects.count(), 1)
        self.assertEqual(Order.objects.get().status, Order.Status.SHIPPED)

    def test_invalid_signature(self):
        self.assertEqual(self.deliver(signature=False).status_code, 400)
        self.assertFalse(Order.objects.exists())

    @override_settings(STRIPE_WEBHOOK_SECRET="")
    def test_missing_webhook_secret(self):
        self.assertEqual(self.deliver().status_code, 503)

    def test_unrelated_event(self):
        self.assertEqual(self.deliver("payment_intent.created").status_code, 200)
        self.assertFalse(Order.objects.exists())

    def test_invalid_data_rolls_back_everything(self):
        cases = [
            {"amount_received": 3000},
            {"shipping": None},
            {"metadata": checkout_metadata([[999999, 2, 1250]], self.user.email)},
            {"metadata": checkout_metadata([[self.product.pk, 2, 1250]], "unknown@example.com")},
            {"metadata": checkout_metadata([[self.product.pk, 0, 1250]], self.user.email)},
        ]
        original = self.intent.copy()
        for changes in cases:
            with self.subTest(changes=changes), patch("cart.views.logger.exception"):
                self.intent = {**original, **changes}
                self.assertEqual(self.deliver().status_code, 422)
                self.assertFalse(Order.objects.exists())
                self.assertFalse(OrderItem.objects.exists())
                self.assertFalse(Address.objects.exists())
                self.assertFalse(CustomerProfile.objects.exists())

    def test_ambiguous_email_is_rejected(self):
        get_user_model().objects.create_user(username="duplicate", email=self.user.email.upper())
        with patch("cart.views.logger.exception"):
            self.assertEqual(self.deliver().status_code, 422)
        self.assertFalse(Order.objects.exists())

    @patch("cart.views.stripe.checkout.Session.create")
    @patch("cart.views.stripe.Price.retrieve")
    def test_checkout_places_purchased_items_in_payment_event(self, retrieve, create):
        retrieve.return_value = stripe.Price.construct_from({"unit_amount": 1250, "currency": "usd", "billing_scheme": "per_unit", "type": "one_time"}, "sk_test")
        create.return_value.url = "https://checkout.stripe.com/test"
        customer = CustomerProfile.objects.create(user=self.user)
        cart = Cart.objects.create(customer=customer)
        variant = ProductVariant.objects.create(product=self.product, color="blue", stock=5)
        CartItem.objects.create(cart=cart, variant=variant, quantity=2)
        self.client.force_login(self.user)
        response = self.client.post(reverse("cart:checkout"))
        self.assertEqual(response.status_code, 302)
        data = create.call_args.kwargs
        self.assertEqual(data["customer_email"], self.user.email)
        self.assertEqual(data["payment_intent_data"]["metadata"],
                         checkout_metadata([[self.product.pk, 2, 1250]], self.user.email, self.user.pk))
        self.assertIn("BD", data["shipping_address_collection"]["allowed_countries"])
        cart.items.all().delete()
        self.intent["metadata"] = data["payment_intent_data"]["metadata"]
        self.assertEqual(self.deliver().status_code, 200)
        self.assertEqual(OrderItem.objects.get().quantity, 2)

    def test_currency_units(self):
        self.assertEqual(money_from_minor(1200, "usd"), Decimal("12"))
        self.assertEqual(money_from_minor(1200, "jpy"), Decimal("1200"))
        self.assertEqual(money_from_minor(1200, "kwd"), Decimal("1.2"))

    def test_stable_user_id_survives_email_changes_and_duplicates(self):
        self.intent["metadata"] = checkout_metadata(
            [[self.product.pk, 2, 1250]], self.user.email, self.user.pk,
        )
        get_user_model().objects.create_user(username="duplicate", email=self.user.email)
        self.user.email = "changed@example.com"
        self.user.save()
        self.assertEqual(self.deliver().status_code, 200)
        self.assertEqual(Order.objects.get().customer.user_id, self.user.pk)

    def test_malformed_payment_data_is_rejected_atomically(self):
        original = self.intent.copy()
        cases = [
            {"metadata": ["invalid"]},
            {"metadata": {**original["metadata"], "order_schema": "99"}},
            {"shipping": "invalid"},
            {"shipping": {"address": "invalid"}},
            {"shipping": {"address": {"country": "BD", "line1": "x" * 256}}},
            {"currency": "invalid"},
            {"amount_received": True},
            {"id": ""},
        ]
        for changes in cases:
            with self.subTest(changes=changes), patch("cart.views.logger.exception"):
                self.intent = {**original, **changes}
                self.assertEqual(self.deliver().status_code, 422)
                self.assertFalse(Order.objects.exists())
                self.assertFalse(CustomerProfile.objects.exists())
                self.assertFalse(Address.objects.exists())

    def test_success_page_requires_checkout_session(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("cart:checkout_success")), reverse("cart:detail"))

    @patch("cart.views.stripe.checkout.Session.retrieve")
    def test_success_page_checks_ownership_and_payment(self, retrieve):
        customer = CustomerProfile.objects.create(user=self.user)
        cart = Cart.objects.create(customer=customer)
        self.client.force_login(self.user)
        url = reverse("cart:checkout_success") + "?session_id=cs_test"
        retrieve.return_value = stripe.checkout.Session.construct_from(
            {"id": "cs_test", "client_reference_id": "other", "payment_status": "paid"}, "sk_test",
        )
        self.assertRedirects(self.client.get(url), reverse("cart:detail"))
        retrieve.return_value = stripe.checkout.Session.construct_from(
            {"id": "cs_test", "client_reference_id": str(cart.pk), "payment_status": "unpaid"}, "sk_test",
        )
        self.assertContains(self.client.get(url), "Your payment is processing")
        retrieve.return_value["payment_status"] = "paid"
        self.assertContains(self.client.get(url), "Your payment was completed successfully")
        self.assertFalse(Order.objects.exists())

    @patch("cart.views.stripe.checkout.Session.retrieve")
    def test_paid_success_page_creates_order_and_clears_cart(self, retrieve):
        customer = CustomerProfile.objects.create(user=self.user)
        cart = Cart.objects.create(customer=customer)
        variant = ProductVariant.objects.create(product=self.product, color="blue", stock=5)
        CartItem.objects.create(cart=cart, variant=variant, quantity=2)
        retrieve.return_value = stripe.checkout.Session.construct_from(
            {
                "id": "cs_paid",
                "client_reference_id": str(cart.pk),
                "payment_status": "paid",
                "payment_intent": self.intent,
                "shipping_details": self.intent["shipping"],
            },
            "sk_test",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("cart:checkout_success") + "?session_id=cs_paid"
        )

        self.assertContains(response, "your order was saved")
        self.assertEqual(Order.objects.count(), 1)
        self.assertFalse(cart.items.exists())

    @patch("cart.views.stripe.checkout.Session.retrieve", side_effect=stripe.APIConnectionError("offline"))
    def test_success_page_handles_stripe_failure(self, retrieve):
        self.client.force_login(self.user)
        self.assertRedirects(
            self.client.get(reverse("cart:checkout_success") + "?session_id=cs_test"),
            reverse("cart:detail"),
        )

    def test_invalid_variant_does_not_crash(self):
        self.client.force_login(self.user)
        for variant_id in ("", "invalid"):
            self.assertRedirects(
                self.client.post(reverse("cart:add"), {"variant_id": variant_id}),
                reverse("products:home"),
            )
