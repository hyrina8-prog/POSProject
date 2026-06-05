from rest_framework import serializers
from django.db import transaction
from .models import User, Customer, Category, Product, StockMovement, Order, OrderItem, Payment


# ============================================================
# USER
# ============================================================

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'phone', 'is_active']
        read_only_fields = ['id']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'email', 'role', 'phone']
        read_only_fields = ['id']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)


# ============================================================
# CUSTOMER
# ============================================================

class CustomerSerializer(serializers.ModelSerializer):
    orders_count = serializers.SerializerMethodField()
    
    # ✅ FRONTEND ALIASES
    customerName = serializers.CharField(source='name')
    customerPhone = serializers.CharField(source='phone', allow_blank=True, required=False, default='')
    customerAddr = serializers.CharField(source='address', allow_blank=True, required=False, default='')

    class Meta:
        model = Customer
        fields = ['id', 'customerName', 'customerPhone', 'customerAddr', 'orders_count', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_orders_count(self, obj):
        return obj.orders.count()


# ============================================================
# CATEGORY
# ============================================================

class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()
    
    # ✅ FRONTEND ALIASES (Read AND Write)
    categoryName = serializers.CharField(source='name')
    categoryImage = serializers.ImageField(source='image', allow_null=True, required=False)

    class Meta:
        model = Category
        fields = ['id', 'categoryName', 'description', 'categoryImage', 'products_count', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_products_count(self, obj):
        return obj.products.filter(is_active=True).count()


# ============================================================
# PRODUCT
# ============================================================

class ProductSerializer(serializers.ModelSerializer):
    # ✅ FRONTEND READ/WRITE ALIASES
    productName = serializers.CharField(source='name')
    productImage = serializers.ImageField(source='image', allow_null=True, required=False)
    
    # ✅ FRONTEND READ-ONLY ALIASES
    categoryName = serializers.CharField(source='category.name', read_only=True, default=None)
    categoryID = serializers.IntegerField(source='category.id', read_only=True, default=None)

    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()

    # ✅ WRITE-ONLY for Forms
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True,
        allow_null=True,
        required=False
    )

    class Meta:
        model = Product
        fields = [
            'id', 
            'productName', 'barcode', 'price', 'stock',
            'categoryName', 'categoryID', 'category_id',
            'description', 'productImage',
            'is_low_stock', 'is_out_of_stock',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductMinimalSerializer(serializers.ModelSerializer):
    """Lightweight serializer for embedding in order items."""
    productName = serializers.CharField(source='name')
    is_low_stock = serializers.ReadOnlyField()       # ← ADD THIS

    class Meta:
        model = Product
        fields = ['id', 'productName', 'barcode', 'price', 'stock', 'is_low_stock']   # ← ADD is_low_stock


        


# ============================================================
# STOCK MOVEMENT
# ============================================================

class StockMovementSerializer(serializers.ModelSerializer):
    product = ProductMinimalSerializer(read_only=True)
    
    # ✅ FRONTEND READ ALIASES
    productName = serializers.CharField(source='product.name', read_only=True)
    moveType = serializers.CharField(source='movement_type', read_only=True)
    moveDate = serializers.DateTimeField(source='created_at', read_only=True)

    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    
    reason = serializers.CharField(required=False, allow_blank=True)
    
    created_by = UserSerializer(read_only=True)
    movement_direction = serializers.ReadOnlyField()

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_id',
            'movement_type', 'reason',
            'quantity', 'note', 'reference',
            'movement_direction',
            'created_by',
            'created_at',
            'productName', 'moveType', 'moveDate'
        ]
        read_only_fields = ['id', 'created_at', 'movement_direction']

    def validate(self, data):
        movement_type = data.get('movement_type')
        reason = data.get('reason')
        
        if reason:
            in_reasons = [r.value for r in StockMovement.Reason.in_reasons()]
            out_reasons = [r.value for r in StockMovement.Reason.out_reasons()]
            if reason in in_reasons:
                data['movement_type'] = StockMovement.MovementType.IN
            elif reason in out_reasons:
                data['movement_type'] = StockMovement.MovementType.OUT
            else:
                raise serializers.ValidationError({'reason': 'Invalid reason provided.'})
        
        elif movement_type:
            if movement_type == StockMovement.MovementType.IN or movement_type == 'in':
                data['movement_type'] = StockMovement.MovementType.IN
                data['reason'] = StockMovement.Reason.ADJUSTMENT_IN
            elif movement_type == StockMovement.MovementType.OUT or movement_type == 'out':
                data['movement_type'] = StockMovement.MovementType.OUT
                data['reason'] = StockMovement.Reason.ADJUSTMENT_OUT
        else:
            raise serializers.ValidationError({"error": "Reason or movement_type is required."})

        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


# ============================================================
# ORDER ITEM
# ============================================================

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductMinimalSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    
    price = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        required=False, 
        allow_null=True,
        default=None
    )

    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'product', 'product_id',
            'quantity', 'price', 'subtotal',
            'created_at'
        ]
        read_only_fields = ['id', 'subtotal', 'created_at', 'order']

    def validate(self, data):
        product = data.get('product')
        quantity = data.get('quantity', 0)

        if product and quantity > 0:
            if product.stock < quantity:
                raise serializers.ValidationError({
                    'quantity': f'Insufficient stock for "{product.name}". Available: {product.stock}'
                })
        return data

    def create(self, validated_data):
        product = validated_data.get('product')
        if validated_data.get('price') is None:
            validated_data['price'] = product.price
            
        return super().create(validated_data)


# ============================================================
# PAYMENT
# ============================================================

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'payment_method',
            'amount_paid', 'change',
            'created_at'
        ]
        read_only_fields = ['id', 'change', 'created_at']

    def validate(self, data):
        order = data.get('order')
        amount_paid = data.get('amount_paid')

        if order and amount_paid is not None:
            if amount_paid < order.grand_total:
                raise serializers.ValidationError({
                    'amount_paid': f'Amount paid ({amount_paid}) is less than grand total ({order.grand_total}).'
                })
            if order.status == 'completed':
                raise serializers.ValidationError({'order': 'This order is already paid.'})
            if order.status == 'cancelled':
                raise serializers.ValidationError({'order': 'Cannot pay for a cancelled order.'})

        return data


# ============================================================
# ORDER
# ============================================================

class OrderItemInlineSerializer(serializers.ModelSerializer):
    """Used inside OrderSerializer to show full item details."""
    product = ProductMinimalSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemInlineSerializer(many=True, read_only=True)
    cashier = UserSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)

    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        source='customer',
        write_only=True,
        allow_null=True,
        required=False
    )

    # ✅ FIX: Explicitly declare tax and discount as read-only
    # This prevents DRF from auto-generating validators from the model
    tax = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status',
            'cashier', 'customer', 'customer_id',
            'items', 'payment',
            'subtotal', 'discount', 'tax', 'grand_total',
            'note',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order_number', 'status',
            'subtotal', 'grand_total',
            'created_at', 'updated_at'
        ]

    def create(self, validated_data):
        validated_data['cashier'] = self.context['request'].user
        return super().create(validated_data)


class OrderCreateSerializer(serializers.ModelSerializer):
    """Used for creating a new order with optional items in one request."""

    class ItemInput(serializers.Serializer):
        product_id = serializers.PrimaryKeyRelatedField(
            queryset=Product.objects.all(),
            source='product'
        )
        quantity = serializers.IntegerField(min_value=1)

    items = ItemInput(many=True, required=False, write_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        source='customer',
        allow_null=True,
        required=False
    )

    # ✅ FIX: Explicitly declare tax and discount WITHOUT max_value
    # This overrides any hidden validators from the model/CoreModel
    tax = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        default=0,
        min_value=0
    )
    discount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        default=0,
        min_value=0
    )

    class Meta:
        model = Order
        fields = ['id', 'customer_id', 'discount', 'tax', 'note', 'items']
        read_only_fields = ['id']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        validated_data['cashier'] = self.context['request'].user

        with transaction.atomic():
            order = Order.objects.create(**validated_data)

            for item_data in items_data:
                product = item_data['product']
                quantity = item_data['quantity']

                if product.stock < quantity:
                    raise serializers.ValidationError({
                        'items': f'Insufficient stock for "{product.name}". Available: {product.stock}'
                    })

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price
                )

            # Recalculate after all items added
            order.calculate_totals()
            order.save(update_fields=['subtotal', 'grand_total'])

        return order


# ============================================================
# RECEIPT (read-only, for printing)
# ============================================================

class ReceiptSerializer(serializers.ModelSerializer):
    """Full order receipt — used for print/invoice endpoint."""
    items = OrderItemInlineSerializer(many=True, read_only=True)
    cashier = UserSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status',
            'cashier', 'customer',
            'items',
            'subtotal', 'discount', 'tax', 'grand_total',
            'payment',
            'note', 'created_at'
        ]