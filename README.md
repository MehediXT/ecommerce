# E-commerce Store

A Django storefront for browsing a product catalog, filtering products, managing an authenticated shopping cart, and starting a Stripe-hosted checkout session.

## Features

- Product categories, products, images, and stock-aware variants
- Search by product name, description, or category
- Category, minimum-price, and maximum-price filters
- Product detail pages with available variant selection
- User registration, login, logout, and profile pages
- Authenticated carts with add and remove actions
- Stripe Checkout sessions using each product's stored Stripe Price ID
- Django admin management for catalog, customer, and cart data
- `seed_products` command for an eight-category sample catalog with 96 products

## Project status

Stripe Checkout is connected, but the application does not yet persist orders, decrement inventory after payment, or process Stripe webhook events. The webhook endpoint currently acknowledges POST requests only. Wishlist and review functionality has not been implemented.

## Tech stack

- Python 3.14
- Django 6.1
- PostgreSQL
- Pillow for image uploads
- Stripe Python SDK

## Prerequisites

- Python 3.14 or another Python version supported by the pinned dependencies
- PostgreSQL running locally or on an accessible server
- Stripe test-mode API keys if checkout is required
- Internet access when running the sample-data seeder, because it downloads placeholder images from Picsum

## Setup

Create and activate a virtual environment, then install the pinned dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requerment.txt
```

The dependency file is currently named `requerment.txt`.

Create a PostgreSQL database named `ecommerce`, or update the `DATABASES` configuration in `ecommerce/settings.py` to match your local database. The default development configuration expects:

```text
database: ecommerce
user: postgres
password: password
host: localhost
port: 5432
```

For Stripe Checkout, create a local `.env` file in the project root or export the variables in your shell:

```text
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
```

Keep secret keys out of version control. Checkout requires `STRIPE_SECRET_KEY`; product records also need a Stripe Price ID before they can be purchased online.

Apply migrations and create an administrator:

```bash
python manage.py migrate
python manage.py createsuperuser
```

Optionally populate the store with sample data:

```bash
python manage.py seed_products
```

The command creates or updates eight categories, 96 products, one default variant per product, and placeholder product images under `media/products/images/`. Running it again does not duplicate existing products or images. The generated sample products do not include Stripe Price IDs, so add those IDs in the admin before testing checkout.

Start the development server:

```bash
python manage.py runserver
```

Open the storefront at [http://127.0.0.1:8000/](http://127.0.0.1:8000/) and the admin panel at [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/).

## Main routes

| Route | Purpose |
| --- | --- |
| `/` | Product catalog, search, and filters |
| `/product/<slug>/` | Product details and variant selection |
| `/accounts/register/` | Create an account |
| `/accounts/login/` | Sign in |
| `/accounts/profile/` | View the signed-in user profile |
| `/cart/` | View the signed-in user's cart |
| `/cart/checkout/` | Start a Stripe Checkout session |
| `/cart/webhook/` | Stripe webhook endpoint |
| `/admin/` | Django administration |

## Test the Stripe webhook locally

The repository includes `ngrok.yml` with the Django endpoint configuration. Start Django and ngrok in separate terminals:

```bash
# Terminal 1
source venv/bin/activate
python manage.py runserver 127.0.0.1:8000

# Terminal 2
ngrok start ecommerce \
  --config "$HOME/.config/ngrok/ngrok.yml" \
  --config ./ngrok.yml
```

Register the generated public URL in Stripe with this path:

```text
https://<your-ngrok-host>/cart/webhook/
```

The endpoint currently returns `{"received": true}` and does not verify or process Stripe events yet.

## Useful commands

```bash
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py seed_products
python manage.py test
```

## Project structure

```text
ecommerce/
├── accounts/       # Registration, authentication, profiles, and addresses
├── products/       # Catalog models, storefront, admin, and seed command
├── cart/           # Cart models, checkout, webhook endpoint, and admin
├── templates/      # Shared and page templates
├── media/          # Uploaded and seeded product images (local only)
├── ecommerce/      # Project settings, WSGI/ASGI, and root URLs
├── requerment.txt  # Pinned Python dependencies
└── manage.py       # Django command-line entry point
```
