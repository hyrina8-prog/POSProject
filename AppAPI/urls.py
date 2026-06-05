from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views, reports

router = DefaultRouter()
router.register(r'users',            views.UserViewSet,         basename='user')
router.register(r'customers',        views.CustomerViewSet,     basename='customer')
router.register(r'categories',       views.CategoryViewSet,     basename='category')
router.register(r'products',         views.ProductViewSet,      basename='product')
router.register(r'stock-movements',  views.StockMovementViewSet, basename='stock-movement')
router.register(r'orders',           views.OrderViewSet,        basename='order')
router.register(r'order-items',      views.OrderItemViewSet,    basename='order-item')
router.register(r'payments',         views.PaymentViewSet,      basename='payment')
router.register(r'reports',          reports.ReportViewSet,     basename='report')

urlpatterns = [
    path('login/',  views.login,  name='login'),
    path('logout/', views.logout, name='logout'),
] + router.urls
