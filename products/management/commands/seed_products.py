from decimal import Decimal
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from products.models import Product, ProductCategory, ProductImage


CATEGORIES = {
    "Electronics": [
        ("Wireless Bluetooth Headphones", "59.99"),
        ("Portable Bluetooth Speaker", "39.99"),
        ("Smart Watch", "89.99"),
        ("USB-C Fast Charger", "24.99"),
        ("Mechanical Keyboard", "74.99"),
        ("Wireless Mouse", "29.99"),
        ("1080p Webcam", "49.99"),
        ("Noise Cancelling Earbuds", "69.99"),
        ("Power Bank 20000mAh", "34.99"),
        ("LED Desk Lamp", "27.99"),
        ("Tablet Stand", "19.99"),
        ("Smart Home Plug", "17.99"),
    ],
    "Fashion": [
        ("Classic Cotton T-Shirt", "19.99"),
        ("Slim Fit Jeans", "44.99"),
        ("Casual Oxford Shirt", "34.99"),
        ("Lightweight Hoodie", "39.99"),
        ("Canvas Sneakers", "54.99"),
        ("Leather Belt", "24.99"),
        ("Everyday Backpack", "49.99"),
        ("Polarized Sunglasses", "29.99"),
        ("Wool Blend Scarf", "22.99"),
        ("Sports Cap", "14.99"),
        ("Classic Wristwatch", "79.99"),
        ("Leather Wallet", "32.99"),
    ],
    "Home & Kitchen": [
        ("Ceramic Dinner Set", "64.99"),
        ("Stainless Steel Water Bottle", "18.99"),
        ("Non-Stick Frying Pan", "29.99"),
        ("Cotton Bath Towel Set", "34.99"),
        ("Bamboo Cutting Board", "16.99"),
        ("Glass Storage Container Set", "27.99"),
        ("Scented Soy Candle", "12.99"),
        ("Microfiber Bed Sheet Set", "49.99"),
        ("Kitchen Knife Set", "59.99"),
        ("Wall Mounted Clock", "21.99"),
        ("Reusable Food Wraps", "15.99"),
        ("Decorative Cushion Cover", "11.99"),
    ],
    "Books": [
        ("The Art of Clean Code", "24.99"),
        ("Beginner's Guide to Python", "29.99"),
        ("Modern Web Development", "34.99"),
        ("The Complete Travel Journal", "18.99"),
        ("Everyday Healthy Cooking", "22.99"),
        ("The Little Book of Habits", "16.99"),
        ("World History Illustrated", "39.99"),
        ("Creative Writing Workshop", "19.99"),
        ("Mindful Living", "17.99"),
        ("Business Strategy Basics", "27.99"),
        ("The Beginner's Garden", "21.99"),
        ("Photography Fundamentals", "31.99"),
    ],
    "Sports & Outdoors": [
        ("Yoga Mat", "24.99"),
        ("Adjustable Dumbbell", "69.99"),
        ("Running Shoes", "79.99"),
        ("Insulated Sports Bottle", "21.99"),
        ("Resistance Band Set", "18.99"),
        ("Camping Tent", "119.99"),
        ("Hiking Backpack", "89.99"),
        ("Fitness Jump Rope", "12.99"),
        ("Football", "24.99"),
        ("Cycling Helmet", "54.99"),
        ("Table Tennis Set", "29.99"),
        ("Portable Camping Chair", "44.99"),
    ],
    "Mobile": [
        ("iPhone 15", "699.99"),
        ("Samsung Galaxy S24", "799.99"),
        ("Google Pixel 9", "649.99"),
        ("OnePlus 12", "749.99"),
        ("Xiaomi Redmi Note 13", "249.99"),
        ("Nothing Phone 2", "599.99"),
        ("Motorola Edge 50", "449.99"),
        ("Realme GT 6", "399.99"),
        ("Oppo Reno 12", "499.99"),
        ("Vivo V30", "429.99"),
        ("Nokia G42", "229.99"),
        ("Tecno Camon 30", "279.99"),
    ],
    "AirPods": [
        ("AirPods 2nd Generation", "99.99"),
        ("AirPods 3rd Generation", "149.99"),
        ("AirPods 4", "129.99"),
        ("AirPods 4 with ANC", "179.99"),
        ("AirPods Pro 2nd Generation", "249.99"),
        ("AirPods Max Space Gray", "549.99"),
        ("AirPods Max Silver", "549.99"),
        ("AirPods Max Blue", "549.99"),
        ("AirPods Pro USB-C Case", "79.99"),
        ("AirPods Wireless Charging Case", "69.99"),
        ("AirPods Silicone Ear Tips", "14.99"),
        ("AirPods Protective Case", "19.99"),
    ],
    "Perfume": [
        ("Ocean Breeze Eau de Parfum", "49.99"),
        ("Midnight Oud Eau de Parfum", "79.99"),
        ("Citrus Bloom Eau de Toilette", "39.99"),
        ("Rose Garden Fragrance", "54.99"),
        ("Sandalwood Mist Cologne", "59.99"),
        ("Vanilla Amber Perfume", "44.99"),
        ("Fresh Lavender Spray", "34.99"),
        ("Musk Noir Fragrance", "69.99"),
        ("Jasmine Rain Eau de Parfum", "64.99"),
        ("Cedar Woods Cologne", "57.99"),
        ("Peach Blossom Perfume", "42.99"),
        ("Classic Leather Fragrance", "74.99"),
    ],
}


class Command(BaseCommand):
    help = "Create sample product categories and products."

    @transaction.atomic
    def handle(self, *args, **options):
        product_count = 0
        image_count = 0

        for category_name, products in CATEGORIES.items():
            category_slug = slugify(category_name)
            category, _ = ProductCategory.objects.update_or_create(
                slug=category_slug,
                defaults={"category_name": category_name},
            )

            for product_name, price in products:
                product_slug = slugify(f"{category_name}-{product_name}")
                product, _ = Product.objects.update_or_create(
                    slug=product_slug,
                    defaults={
                        "product_name": product_name,
                        "product_category": category,
                        "description": (
                            f"A sample {product_name.lower()} from the "
                            f"{category_name.lower()} category."
                        ),
                        "price": Decimal(price),
                    },
                )
                product_count += 1

                if not ProductImage.objects.filter(product=product).exists():
                    try:
                        image = ProductImage(product=product)
                        image.image.save(
                            f"{product_slug}.jpg",
                            ContentFile(self.download_image(product_slug)),
                            save=True,
                        )
                        image_count += 1
                    except Exception as error:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Could not download an image for "
                                f"{product_name}: {error}"
                            )
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"{category_name}: {len(products)} sample products ready"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {len(CATEGORIES)} categories and "
                f"{product_count} products ready; {image_count} images added."
            )
        )

    @staticmethod
    def download_image(product_slug):
        image_url = f"https://picsum.photos/seed/{product_slug}/800/800.jpg"
        request = Request(image_url, headers={"User-Agent": "ecommerce-seeder/1.0"})
        with urlopen(request, timeout=20) as response:
            return response.read()
