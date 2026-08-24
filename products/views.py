from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.db.models import Q
from django.shortcuts import render

from .models import Product, ProductCategory


def home(request):
    search_query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    products = Product.objects.select_related("product_category").prefetch_related(
        "images"
    )

    if search_query:
        products = products.filter(
            Q(product_name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(product_category__category_name__icontains=search_query)
        )

    if category_slug:
        products = products.filter(product_category__slug=category_slug)

    for price_value, lookup in ((min_price, "price__gte"), (max_price, "price__lte")):
        if price_value:
            try:
                products = products.filter(**{lookup: Decimal(price_value)})
            except (InvalidOperation, ValueError):
                pass

    return render(
        request,
        "products/home.html",
        {
            "products": products,
            "categories": ProductCategory.objects.all(),
            "search_query": search_query,
            "active_category": category_slug,
            "min_price": min_price,
            "max_price": max_price,
            "clear_filters_query": urlencode(
                {
                    key: value
                    for key, value in {
                        "q": search_query,
                        "category": category_slug,
                    }.items()
                    if value
                }
            ),
        },
    )
