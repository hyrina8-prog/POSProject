from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from decimal import Decimal
import datetime


# ============================================================
# ABSTRACT BASE MODEL
# ============================================================

class CoreModel(models.Model):
    """Abstract base model with audit fields for all POS models."""
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ============================================================
# USER
# ============================================================

class User(AbstractUser):
    """Custom user model with role-based access control."""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        CASHIER = 'cashier', 'Cashier'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CASHIER
    )
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.username} ({self.role})"

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_cashier(self):
        return self.role == self.Role.CASHIER


# ============================================================
# CUSTOMER
# ============================================================

class Customer(CoreModel):
    """Walk-in or registered customers."""
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        db_table = 'customers'
        ordering = ['id']

    def __str__(self):
        return self.name


# ============================================================
# CATEGORY
# ============================================================

class Category(CoreModel):
    """Product categories (e.g. Electronics, Clothing, Food)."""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


# ============================================================
# PRODUCT
# ============================================================

class Product(CoreModel):
    """Retail products available for sale."""
    name = models.CharField(max_length=200)
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    class Meta:
        db_table = 'products'
        ordering = ['id']

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.stock < 10

    @property
    def is_out_of_stock(self):
        return self.stock <= 0

    def clean(self):
        super().clean()
        if self.price is not None and self.price < 0:
            raise ValidationError({'price': 'Price cannot be negative.'})
        if self.stock < 0:
            raise ValidationError({'stock': 'Stock cannot be negative.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


# ============================================================
# STOCK MOVEMENT
# ============================================================

class StockMovement(CoreModel):
    """Audit log for every stock change (in or out)."""

    class MovementType(models.TextChoices):
        IN = 'in', 'Stock In'
        OUT = 'out', 'Stock Out'

    class Reason(models.TextChoices):
        # Stock IN reasons
        PURCHASE = 'purchase', 'Purchase / Restock'
        RETURN_CUSTOMER = 'return_customer', 'Return from Customer'
        ADJUSTMENT_IN = 'adjustment_in', 'Manual Adjustment (In)'
        # Stock OUT reasons
        SALE = 'sale', 'Sale'
        DAMAGED = 'damaged', 'Damaged / Loss'
        ADJUSTMENT_OUT = 'adjustment_out', 'Manual Adjustment (Out)'

        @classmethod
        def in_reasons(cls):
            return [cls.PURCHASE, cls.RETURN_CUSTOMER, cls.ADJUSTMENT_IN]

        @classmethod
        def out_reasons(cls):
            return [cls.SALE, cls.DAMAGED, cls.ADJUSTMENT_OUT]

    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices
    )
    reason = models.CharField(
        max_length=30,
        choices=Reason.choices
    )
    quantity = models.IntegerField()
    note = models.TextField(blank=True)
    reference = models.CharField(max_length=100, blank=True, help_text="Order number or manual ref")
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='stock_movements'
    )

    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.movement_type} | {self.product.name} x {self.quantity}"

    @property
    def is_stock_in(self):
        return self.movement_type == self.MovementType.IN

    def clean(self):
        super().clean()
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be a positive number.'})

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.clean()

        with transaction.atomic():
            super().save(*args, **kwargs)

            # Apply stock change only on creation
            if is_new and self.product:
                if self.is_stock_in:
                    self.product.stock += self.quantity
                else:
                    if self.product.stock < self.quantity:
                        raise ValidationError({
                            'quantity': f'Insufficient stock for {self.product.name}. Available: {self.product.stock}'
                        })
                    self.product.stock -= self.quantity
                self.product.save(update_fields=['stock'])

    def delete(self, *args, **kwargs):
        """Reverse the stock change when a movement is deleted."""
        if self.product:
            if self.is_stock_in:
                self.product.stock -= self.quantity
            else:
                self.product.stock += self.quantity
            self.product.save(update_fields=['stock'])
        super().delete(*args, **kwargs)


# ============================================================
# ORDER
# ============================================================

class Order(CoreModel):
    """A sales transaction at the POS."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    order_number = models.CharField(max_length=30, unique=True, blank=True)
    cashier = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders'
    )
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True)

    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number

    def calculate_totals(self):
        """Recalculate subtotal, tax, and grand_total from order items."""
        self.subtotal = sum(item.subtotal for item in self.items.all())
        self.grand_total = self.subtotal - self.discount + self.tax
        return self.grand_total

    def save(self, *args, **kwargs):
        # Auto-generate order number on first save
        if not self.pk and not self.order_number:
            today = datetime.date.today()
            count = Order.objects.filter(created_at__date=today).count() + 1
            self.order_number = f"ORD-{today.strftime('%Y%m%d')}-{count:04d}"
        super().save(*args, **kwargs)


# ============================================================
# ORDER ITEM
# ============================================================

class OrderItem(CoreModel):
    """A single line item within an Order."""
    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items'
    )
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Unit price at time of sale
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'order_items'

    def __str__(self):
        return f"{self.order.order_number} — {self.product} x {self.quantity}"

    def clean(self):
        super().clean()
        if self.product and self.quantity is not None:
            if self.quantity <= 0:
                raise ValidationError({'quantity': 'Quantity must be at least 1.'})
            if self.product.stock < self.quantity:
                raise ValidationError({
                    'quantity': f'Insufficient stock for "{self.product.name}". Available: {self.product.stock}'
                })

    def save(self, *args, **kwargs):
        # Immutable after creation — to change, delete and recreate
        if self.pk is not None:
            raise ValidationError("OrderItem cannot be updated. Delete it and create a new one.")

        self.clean()
        self.subtotal = Decimal(str(self.quantity)) * Decimal(str(self.price))

        with transaction.atomic():
            super().save(*args, **kwargs)

            # Auto-deduct stock and create stock movement
            if self.product:
                StockMovement.objects.create(
                    product=self.product,
                    movement_type=StockMovement.MovementType.OUT,
                    reason=StockMovement.Reason.SALE,
                    quantity=self.quantity,
                    reference=self.order.order_number,
                    note=f'Auto-deducted from Order #{self.order.order_number}',
                    created_by=self.order.cashier
                )

            # Recalculate order totals
            self.order.calculate_totals()
            self.order.save(update_fields=['subtotal', 'grand_total'])

    def delete(self, *args, **kwargs):
        """Restore stock when an item is removed from an order."""
        with transaction.atomic():
            if self.product:
                # Reverse the sale stock movement
                StockMovement.objects.create(
                    product=self.product,
                    movement_type=StockMovement.MovementType.IN,
                    reason=StockMovement.Reason.RETURN_CUSTOMER,
                    quantity=self.quantity,
                    reference=self.order.order_number,
                    note=f'Stock restored — item removed from Order #{self.order.order_number}',
                    created_by=self.order.cashier
                )

            order = self.order
            super().delete(*args, **kwargs)

            order.calculate_totals()
            order.save(update_fields=['subtotal', 'grand_total'])


# ============================================================
# PAYMENT
# ============================================================
class Payment(CoreModel):
    """Payment record linked to an Order."""

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Cash'
        CARD = 'card', 'Card'
        KHQR = 'khqr', 'KHQR (ABA / ACLEDA)'        # ✅ FIXED: Was 'qr', now matches frontend
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'

    order = models.OneToOneField(
        'Order',
        on_delete=models.CASCADE,
        related_name='payment'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    change = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment for {self.order.order_number} — {self.payment_method}"

    def clean(self):
        super().clean()
        if self.amount_paid < self.order.grand_total:
            raise ValidationError({
                'amount_paid': f'Amount paid ({self.amount_paid}) is less than grand total ({self.order.grand_total}).'
            })

    def save(self, *args, **kwargs):
        self.change = Decimal(str(self.amount_paid)) - Decimal(str(self.order.grand_total))
        self.clean()
        with transaction.atomic():
            super().save(*args, **kwargs)
            # Mark order as completed upon payment
            self.order.status = Order.Status.COMPLETED
            self.order.save(update_fields=['status'])
