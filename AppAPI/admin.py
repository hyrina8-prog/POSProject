from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Customer, Category, Product, StockMovement, Order, OrderItem, Payment


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'first_name', 'last_name', 'email', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('POS Info', {'fields': ('role', 'phone')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('POS Info', {'fields': ('role', 'phone')}),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'address', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'phone']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    fields = ['name', 'description', 'image', 'is_active'] 


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['subtotal', 'created_at']
    fields = ['product', 'quantity', 'price', 'subtotal']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'barcode', 'price', 'stock', 'category', 'is_active', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'barcode']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'movement_type', 'reason', 'quantity', 'reference', 'created_by', 'created_at']
    list_filter = ['movement_type', 'reason']
    search_fields = ['product__name', 'reference']
    readonly_fields = ['created_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'cashier', 'customer', 'status', 'grand_total', 'created_at']
    list_filter = ['status']
    search_fields = ['order_number', 'customer__name', 'cashier__username']
    readonly_fields = ['order_number', 'subtotal', 'grand_total', 'created_at', 'updated_at']
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price', 'subtotal', 'created_at']
    readonly_fields = ['subtotal', 'created_at']
    search_fields = ['order__order_number', 'product__name']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'payment_method', 'amount_paid', 'change', 'created_at']
    list_filter = ['payment_method']
    search_fields = ['order__order_number']
    readonly_fields = ['change', 'created_at']
