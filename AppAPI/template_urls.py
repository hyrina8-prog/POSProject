# template_urls.py
from django.urls import path
from .template_views import (
    login_page,
    logout_page,
    dashboard_page,
    pos_page,
    products_page,
    categories_page,
    customers_page,
    stock_page,
    reports_page,
    users_page,
)

urlpatterns = [
    path('login/',      login_page,      name='template_login'),
    path('logout/',     logout_page,     name='template_logout'),
    path('',  dashboard_page,  name='template_dashboard'),
    path('dashboard/',  dashboard_page,  name='template_dashboard'),
    path('pos/',        pos_page,        name='template_pos'),
    path('products/',   products_page,   name='template_products'),
    path('categories/', categories_page, name='template_categories'),
    path('customers/',  customers_page,  name='template_customers'),
    path('stock/',      stock_page,      name='template_stock'),
    path('reports/',    reports_page,    name='template_reports'),
    path('users/',      users_page,      name='template_users'),
]