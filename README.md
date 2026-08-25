# Ecommerce Store

A Django-based ecommerce storefront for browsing products by category and price. The project includes a product catalog, product categories, product images, product variants, authentication, and a responsive home page.

## Current features

- Product categories and products managed through Django admin
- Product images and product variants
- Responsive product listing at `/`
- Product search by name, description, or category
- Category filtering
- Minimum and maximum price filtering
- Product detail pages with variant selection
- Authenticated shopping cart with add and remove actions
- Stripe hosted Checkout using each product's stored Stripe Price ID
- Login, registration, profile, and logout flows
- Sample catalog seeding with 8 categories and 96 products
- Seeded placeholder images downloaded from the internet

## Still in progress

- Orders and payment processing
- Customer wishlist and reviews

## Setup

Create and activate a virtual environment, then install the dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requerment.txt
```

Set the Stripe keys in the environment (or in a local `.env` file):

```text
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
```

The project is configured for PostgreSQL. Update the database settings in `ecommerce/settings.py` for your local PostgreSQL database before running migrations.

Run the migrations:

```bash
python manage.py migrate
```

Create an admin user:

```bash
python manage.py createsuperuser
```

Start the development server:

```bash
python manage.py runserver
```

Open the storefront at [http://127.0.0.1:8000/](http://127.0.0.1:8000/) and the admin panel at [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/).

## Test the Stripe webhook locally

ngrok is configured with the project endpoint in `ngrok.yml`. Start Django and ngrok in separate terminals:

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

The endpoint currently acknowledges POST requests and does not process events yet.

## Add sample products

After PostgreSQL is running and migrations are applied, run:

```bash
python manage.py seed_products
```

This command creates or updates the sample categories and products. It also downloads one placeholder image per product into `media/products/images/`. Running the command again does not create duplicate products or images.

## Project structure

```text
ecommerce/
├── accounts/       # Registration, login, logout, and profile
├── products/       # Product models, storefront, admin, and seed command
├── cart/           # Cart and cart-item models, views, and admin
├── templates/      # Shared and page templates
├── media/          # Uploaded and seeded product images
├── ecommerce/      # Django project settings and URLs
└── manage.py
```

## Useful commands

```bash
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py seed_products
```
