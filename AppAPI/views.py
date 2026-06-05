
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q, Sum
from rest_framework import viewsets, status, serializers as drf_serializers
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse, OpenApiParameter

from .models import User, Customer, Category, Product, StockMovement, Order, OrderItem, Payment
from .serializers import (
    UserSerializer, UserCreateSerializer, ChangePasswordSerializer,
    CustomerSerializer, CategorySerializer,
    ProductSerializer, ProductMinimalSerializer,
    StockMovementSerializer,
    OrderSerializer, OrderCreateSerializer, OrderItemSerializer,
    PaymentSerializer, ReceiptSerializer
)
from .permissions import IsAdmin, IsCashier, IsAdminOrCashier, IsAdminOrReadOnly, IsOwnerOrAdmin


# ============================================================
# AUTH
# ============================================================

@extend_schema(
    tags=['Auth'],
    request=inline_serializer(
        name='LoginRequest',
        fields={
            'username': drf_serializers.CharField(),
            'password': drf_serializers.CharField(),
        }
    ),
    responses={
        200: inline_serializer(
            name='LoginResponse',
            fields={
                'token': drf_serializers.CharField(),
                'user_id': drf_serializers.IntegerField(),
                'username': drf_serializers.CharField(),
                'role': drf_serializers.CharField(),
            }
        ),
        401: OpenApiResponse(description='Invalid Credentials')
    },
    auth=None
)
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def login(request):
    """Authenticate with username/password and receive an auth token."""
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)

    if user:
        if not user.is_active:
            return Response({'error': 'Account is disabled.'}, status=status.HTTP_403_FORBIDDEN)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'first_name': user.first_name,
            'last_name': user.last_name,
        })
    return Response({'error': 'Invalid username or password.'}, status=status.HTTP_401_UNAUTHORIZED)


@extend_schema(tags=['Auth'])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Delete the auth token (logout)."""
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    return Response({'message': 'Logged out successfully.'})


# ============================================================
# USER
# ============================================================

class UserViewSet(viewsets.ModelViewSet):
    """
    Admin: full CRUD on users.
    Any authenticated user: GET /users/me/
    """
    queryset = User.objects.all().order_by('-date_joined')

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action == 'me':
            return [IsAuthenticated()]
        if self.action == 'change_password':
            return [IsAuthenticated()]
        return [IsAdmin()]

    @extend_schema(responses=UserSerializer)
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Return the currently authenticated user's profile."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(request=ChangePasswordSerializer, responses={200: None})
    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        """Allow a user to change their own password."""
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not request.user.check_password(serializer.validated_data['old_password']):
            return Response({'error': 'Old password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        # Re-issue token after password change
        Token.objects.filter(user=request.user).delete()
        token, _ = Token.objects.get_or_create(user=request.user)
        return Response({'message': 'Password changed successfully.', 'token': token.key})


# ============================================================
# CUSTOMER
# ============================================================

class CustomerViewSet(viewsets.ModelViewSet):
    """
    Admin: full CRUD.
    Cashier: list, retrieve, create.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    def get_permissions(self):
        if self.action in ['destroy', 'update', 'partial_update']:
            return [IsAdmin()]
        return [IsAdminOrCashier()]

    def get_queryset(self):
        queryset = Customer.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(phone__icontains=search)
            )
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


# ============================================================
# CATEGORY
# ============================================================

class CategoryViewSet(viewsets.ModelViewSet):
    """
    Admin: full CRUD.
    Cashier: read-only.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = Category.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all active products under this category."""
        category = self.get_object()
        products = category.products.filter(is_active=True)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


# ============================================================
# PRODUCT
# ============================================================

class ProductViewSet(viewsets.ModelViewSet):
    """
    Admin: full CRUD + stock management.
    Cashier: read-only + barcode scan.
    """
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = Product.objects.select_related('category').all()

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(barcode__icontains=search) |
                Q(description__icontains=search)
            )

        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        low_stock = self.request.query_params.get('low_stock')
        if low_stock and low_stock.lower() == 'true':
            queryset = queryset.filter(stock__lt=10)

        out_of_stock = self.request.query_params.get('out_of_stock')
        if out_of_stock and out_of_stock.lower() == 'true':
            queryset = queryset.filter(stock=0)

        return queryset

    @extend_schema(
        parameters=[OpenApiParameter('barcode', str, description='Product barcode to scan')],
        responses=ProductSerializer
    )
    @action(detail=False, methods=['get'])
    def scan(self, request):
        """
        Look up a product by barcode.
        Usage: GET /api/products/scan/?barcode=123456789
        """
        barcode = request.query_params.get('barcode')
        if not barcode:
            return Response({'error': 'barcode query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(barcode=barcode, is_active=True)
            serializer = ProductSerializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({'error': f'No product found with barcode: {barcode}'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        request=inline_serializer(
            name='StockAdjustRequest',
            fields={
                'quantity': drf_serializers.IntegerField(),
                'reason': drf_serializers.CharField(),
                'note': drf_serializers.CharField(required=False),
            }
        ),
        responses=ProductSerializer
    )
    @action(detail=True, methods=['post'], url_path='adjust-stock', permission_classes=[IsAdmin])
    def adjust_stock(self, request, pk=None):
        """
        Manually adjust stock for a product.
        Positive quantity = stock IN, Negative = stock OUT.
        """
        product = self.get_object()
        quantity = request.data.get('quantity')
        reason = request.data.get('reason')
        note = request.data.get('note', '')

        if quantity is None:
            return Response({'error': 'quantity is required.'}, status=status.HTTP_400_BAD_REQUEST)

        quantity = int(quantity)
        if quantity == 0:
            return Response({'error': 'quantity cannot be 0.'}, status=status.HTTP_400_BAD_REQUEST)

        if quantity > 0:
            movement_type = StockMovement.MovementType.IN
            if not reason:
                reason = StockMovement.Reason.ADJUSTMENT_IN
        else:
            movement_type = StockMovement.MovementType.OUT
            quantity = abs(quantity)
            if not reason:
                reason = StockMovement.Reason.ADJUSTMENT_OUT

        try:
            StockMovement.objects.create(
                product=product,
                movement_type=movement_type,
                reason=reason,
                quantity=quantity,
                note=note,
                created_by=request.user
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        product.refresh_from_db()
        serializer = ProductSerializer(product)
        return Response(serializer.data)


# ============================================================
# STOCK MOVEMENT
# ============================================================

class StockMovementViewSet(viewsets.ModelViewSet):
    """
    Admin: full CRUD for stock movements.
    Cashier: read-only.
    """
    queryset = StockMovement.objects.select_related('product', 'created_by').all()
    serializer_class = StockMovementSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdmin()]

    def get_queryset(self):
        queryset = StockMovement.objects.select_related('product', 'created_by').all()

        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        movement_type = self.request.query_params.get('movement_type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)

        reason = self.request.query_params.get('reason')
        if reason:
            queryset = queryset.filter(reason=reason)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        return queryset
    
 # ✅ NEW ACTION — uses database aggregation, not paginated list
    @extend_schema(tags=['Stock Movements'])
    @action(detail=False, methods=['get'], url_path='today-summary')
    def today_summary(self, request):
        """
        GET /api/stock-movements/today-summary/
        Returns total stock in and out for today using database aggregation.
        Always accurate regardless of pagination.
        """
        from django.utils import timezone

        today = timezone.now().date()
        movements = StockMovement.objects.filter(created_at__date=today)

        total_in = movements.filter(
            movement_type=StockMovement.MovementType.IN
        ).aggregate(total=Sum('quantity'))['total'] or 0

        total_out = movements.filter(
            movement_type=StockMovement.MovementType.OUT
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return Response({
            'total_in': total_in,
            'total_out': total_out,
        })



# ============================================================
# ORDER
# ============================================================

class OrderViewSet(viewsets.ModelViewSet):
    """
    Admin: full access including cancellation and delete.
    Cashier: create orders, add items, checkout, view own orders.
    """
    queryset = Order.objects.select_related('cashier', 'customer').prefetch_related('items', 'items__product').all()

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        if self.action in ['receipt', 'retrieve']:
            return ReceiptSerializer
        return OrderSerializer

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAdmin()]
        return [IsAdminOrCashier()]

    def get_queryset(self):
        queryset = Order.objects.select_related('cashier', 'customer') \
            .prefetch_related('items', 'items__product').all()

        # Cashiers only see their own orders
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(cashier=self.request.user)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        cashier_id = self.request.query_params.get('cashier_id')
        if cashier_id and self.request.user.role == 'admin':
            queryset = queryset.filter(cashier_id=cashier_id)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        return queryset

    @extend_schema(
        request=inline_serializer(
            name='CheckoutRequest',
            fields={
                'payment_method': drf_serializers.CharField(),
                'amount_paid': drf_serializers.DecimalField(max_digits=12, decimal_places=2),
            }
        ),
        responses=ReceiptSerializer
    )
    @action(detail=True, methods=['post'])
    def checkout(self, request, pk=None):
        """
        Finalize an order — create payment and mark as completed.
        POST /api/orders/{id}/checkout/
        Body: { "payment_method": "cash", "amount_paid": 100000 }
        """
        order = self.get_object()

        if order.status == Order.Status.COMPLETED:
            return Response({'error': 'Order is already completed.'}, status=status.HTTP_400_BAD_REQUEST)
        if order.status == Order.Status.CANCELLED:
            return Response({'error': 'Cannot checkout a cancelled order.'}, status=status.HTTP_400_BAD_REQUEST)
        if not order.items.exists():
            return Response({'error': 'Order has no items.'}, status=status.HTTP_400_BAD_REQUEST)

        payment_data = {
            'order': order.id,
            'payment_method': request.data.get('payment_method', 'cash'),
            'amount_paid': request.data.get('amount_paid'),
        }

        serializer = PaymentSerializer(data=payment_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        order.refresh_from_db()
        receipt_serializer = ReceiptSerializer(order)
        return Response(receipt_serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel a pending order and restore all stock.
        POST /api/orders/{id}/cancel/
        """
        order = self.get_object()

        if order.status != Order.Status.PENDING:
            return Response(
                {'error': f'Cannot cancel an order with status "{order.status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Restore stock for each item
            for item in order.items.all():
                if item.product:
                    StockMovement.objects.create(
                        product=item.product,
                        movement_type=StockMovement.MovementType.IN,
                        reason=StockMovement.Reason.RETURN_CUSTOMER,
                        quantity=item.quantity,
                        reference=order.order_number,
                        note=f'Stock restored — Order #{order.order_number} cancelled',
                        created_by=request.user
                    )
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])

        serializer = OrderSerializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        """
        Get the full printable receipt for an order.
        GET /api/orders/{id}/receipt/
        """
        order = self.get_object()
        serializer = ReceiptSerializer(order)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """List all items in an order."""
        order = self.get_object()
        items = order.items.select_related('product').all()
        serializer = OrderItemSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='add-item')
    def add_item(self, request, pk=None):
        """
        Add a single item to a pending order.
        POST /api/orders/{id}/add-item/
        Body: { "product_id": 1, "quantity": 2 }
        """
        order = self.get_object()

        if order.status != Order.Status.PENDING:
            return Response(
                {'error': f'Cannot add items to an order with status "{order.status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()
        data['order'] = order.id

        serializer = OrderItemSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(order=order)

        order.refresh_from_db()
        order_serializer = OrderSerializer(order)
        return Response(order_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='remove-item/(?P<item_id>[^/.]+)')
    def remove_item(self, request, pk=None, item_id=None):
        """
        Remove a specific item from a pending order.
        DELETE /api/orders/{id}/remove-item/{item_id}/
        """
        order = self.get_object()

        if order.status != Order.Status.PENDING:
            return Response(
                {'error': f'Cannot remove items from an order with status "{order.status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            item = order.items.get(id=item_id)
            item.delete()
        except OrderItem.DoesNotExist:
            return Response({'error': 'Item not found in this order.'}, status=status.HTTP_404_NOT_FOUND)

        order.refresh_from_db()
        serializer = OrderSerializer(order)
        return Response(serializer.data)


# ============================================================
# ORDER ITEM (standalone)
# ============================================================

class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to order items. Use OrderViewSet actions to create/delete."""
    queryset = OrderItem.objects.select_related('product', 'order').all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsAdminOrCashier]

    def get_queryset(self):
        queryset = OrderItem.objects.select_related('product', 'order').all()
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(order__cashier=self.request.user)
        order_id = self.request.query_params.get('order_id')
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset


# ============================================================
# PAYMENT
# ============================================================

class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to payments. Payments are created via the checkout action."""
    queryset = Payment.objects.select_related('order').all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminOrCashier]

    def get_queryset(self):
        queryset = Payment.objects.select_related('order').all()
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(order__cashier=self.request.user)
        payment_method = self.request.query_params.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset
    


# ============================================================
# REPORTS
# ============================================================

@extend_schema(tags=['Reports'])
@api_view(['GET'])
@permission_classes([IsAdmin])
def daily_sales_report(request):
    """GET /api/reports/daily/?date=YYYY-MM-DD"""
    date_str = request.query_params.get('date')
    if not date_str:
        return Response({"error": "Date parameter is required (YYYY-MM-DD)"}, status=400)
    
    orders = Order.objects.filter(created_at__date=date_str, status=Order.Status.COMPLETED)
    total_sales = orders.aggregate(total=Sum('grand_total'))['total'] or 0
    total_orders = orders.count()
    
    return Response({
        "totalSales": total_sales,
        "totalOrders": total_orders
    })


@extend_schema(tags=['Reports'])
@api_view(['GET'])
@permission_classes([IsAdmin])
def monthly_sales_report(request):
    """GET /api/reports/monthly/?year=YYYY&month=MM"""
    year = request.query_params.get('year')
    month = request.query_params.get('month')
    if not year or not month:
        return Response({"error": "Year and month parameters are required"}, status=400)
    
    orders = Order.objects.filter(
        created_at__year=year, 
        created_at__month=month, 
        status=Order.Status.COMPLETED
    )
    total_sales = orders.aggregate(total=Sum('grand_total'))['total'] or 0
    total_orders = orders.count()
    unique_customers = orders.values('customer').distinct().count()
    
    return Response({
        "totalSales": total_sales,
        "totalOrders": total_orders,
        "uniqueCustomers": unique_customers
    })


@extend_schema(tags=['Reports'])
@api_view(['GET'])
@permission_classes([IsAdmin])
def low_stock_report(request):
    """GET /api/reports/low-stock/ — uses the same stock__lt=10 as the model's is_low_stock property."""
    threshold = int(request.query_params.get('threshold', 10))
    products = Product.objects.filter(stock__lt=threshold, is_active=True)

    serializer = ProductMinimalSerializer(products, many=True)
    return Response(serializer.data)