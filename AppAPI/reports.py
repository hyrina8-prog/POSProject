from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Avg, F, Q, DecimalField
from django.db.models.functions import TruncDate, TruncMonth, Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from .models import Order, OrderItem, Product, StockMovement, Customer, Payment
from .permissions import IsAdmin


def safe_int(value, default):
    """Prevent 500 errors from bad query parameters."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class ReportViewSet(viewsets.ViewSet):
    """
    Analytics and reporting endpoints for the POS system.
    All reports require authentication. Some are Admin-only.
    """
    permission_classes = [IsAuthenticated]

    # --------------------------------------------------------
    # DAILY (Used by reports.html)
    # --------------------------------------------------------

    @extend_schema(
        parameters=[OpenApiParameter('date', str, description='Target date (YYYY-MM-DD)')],
        responses=inline_serializer(name='DailyReportResponse', fields={
            'date': serializers.CharField(),
            'totalSales': serializers.DecimalField(max_digits=12, decimal_places=2),
            'totalOrders': serializers.IntegerField(),
        })
    )
    @action(detail=False, methods=['get'])
    def daily(self, request):
        """Usage: GET /api/reports/daily/?date=2025-01-01"""
        date_str = request.query_params.get('date')
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
        else:
            target_date = timezone.now().date()

        orders = Order.objects.filter(status='completed', created_at__date=target_date)
        total_sales = orders.aggregate(total=Sum('grand_total'))['total'] or 0
        total_orders = orders.count()

        return Response({
            'date': str(target_date),
            'totalSales': total_sales,
            'totalOrders': total_orders,
        })

    # --------------------------------------------------------
    # MONTHLY (Used by reports.html) ✅ ADDED
    # --------------------------------------------------------

    @extend_schema(
        parameters=[
            OpenApiParameter('year', int, description='Year (e.g. 2026)'),
            OpenApiParameter('month', int, description='Month (1-12)'),
        ],
        responses=inline_serializer(name='MonthlyReportResponse', fields={
            'totalSales': serializers.DecimalField(max_digits=12, decimal_places=2),
            'totalOrders': serializers.IntegerField(),
            'uniqueCustomers': serializers.IntegerField(),
        })
    )
    @action(detail=False, methods=['get'])
    def monthly(self, request):
        """Usage: GET /api/reports/monthly/?year=2026&month=5"""
        year = safe_int(request.query_params.get('year'), timezone.now().year)
        month = safe_int(request.query_params.get('month'), timezone.now().month)

        orders = Order.objects.filter(
            status='completed', 
            created_at__year=year, 
            created_at__month=month
        )
        
        total_sales = orders.aggregate(total=Sum('grand_total'))['total'] or 0
        total_orders = orders.count()
        unique_customers = orders.values('customer').distinct().count()

        return Response({
            'totalSales': total_sales,
            'totalOrders': total_orders,
            'uniqueCustomers': unique_customers
        })

    # --------------------------------------------------------
    # LOW STOCK (Used by reports.html & stock.html) ✅ UPDATED
    # --------------------------------------------------------

    @extend_schema(
        parameters=[OpenApiParameter('threshold', int, description='Low stock threshold (default: 5)')]
    )
    @action(detail=False, methods=['get'], url_path='low-stock')
    def low_stock(self, request):
        """Usage: GET /api/reports/low-stock/?threshold=5"""
        threshold = safe_int(request.query_params.get('threshold'), 5)
        
        # ✅ CHANGED: Use values() and annotate with productName to match frontend JS
        products = list(
            Product.objects
            .filter(is_active=True, stock__lte=threshold, stock__gt=0)
            .annotate(productName=F('name'))
            .values('id', 'productName', 'stock', 'barcode')
            .order_by('stock')
        )

        return Response(products)

    # --------------------------------------------------------
    # (Keep all your other existing actions below exactly as they were)
    # --------------------------------------------------------

    @extend_schema(
        parameters=[
            OpenApiParameter('start_date', str, description='Filter from date (YYYY-MM-DD)'),
            OpenApiParameter('end_date', str, description='Filter to date (YYYY-MM-DD)'),
        ]
    )
    @action(detail=False, methods=['get'])
    def sales_summary(self, request):
        orders = Order.objects.filter(status='completed')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date: orders = orders.filter(created_at__date__gte=start_date)
        if end_date: orders = orders.filter(created_at__date__lte=end_date)

        summary = orders.aggregate(
            total_orders=Count('id'),
            total_revenue=Coalesce(Sum('grand_total'), 0, output_field=DecimalField()),
            total_discount=Coalesce(Sum('discount'), 0, output_field=DecimalField()),
            avg_order_value=Avg('grand_total'),
        )
        daily_breakdown = (
            orders.annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(orders_count=Count('id'), revenue=Coalesce(Sum('grand_total'), 0, output_field=DecimalField()), discount_given=Coalesce(Sum('discount'), 0, output_field=DecimalField()))
            .order_by('date')
        )
        return Response({
            'summary': {
                'total_orders': summary['total_orders'] or 0,
                'total_revenue': summary['total_revenue'] or 0,
                'total_discount': summary['total_discount'] or 0,
                'average_order_value': round(summary['avg_order_value'] or 0, 2),
            },
            'daily_breakdown': list(daily_breakdown),
        })

    @extend_schema(parameters=[OpenApiParameter('year', int)])
    @action(detail=False, methods=['get'])
    def monthly_revenue(self, request):
        year = safe_int(request.query_params.get('year'), timezone.now().year)
        monthly = (
            Order.objects.filter(status='completed', created_at__year=year)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(orders_count=Count('id'), revenue=Coalesce(Sum('grand_total'), 0, output_field=DecimalField()), discount_given=Coalesce(Sum('discount'), 0, output_field=DecimalField()))
            .order_by('month')
        )
        return Response({'year': year, 'monthly_data': list(monthly)})

    @extend_schema(parameters=[OpenApiParameter('limit', int), OpenApiParameter('start_date', str), OpenApiParameter('end_date', str)])
    @action(detail=False, methods=['get'])
    def top_products(self, request):
        limit = safe_int(request.query_params.get('limit'), 10)
        items = OrderItem.objects.filter(order__status='completed')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date: items = items.filter(order__created_at__date__gte=start_date)
        if end_date: items = items.filter(order__created_at__date__lte=end_date)
        top = (
            items.values('product__id', 'product__name', 'product__barcode', 'product__category__name')
            .annotate(total_quantity_sold=Sum('quantity'), total_revenue=Sum('subtotal'))
            .order_by('-total_quantity_sold')[:limit]
        )
        return Response({'top_products': list(top)})

    @extend_schema(parameters=[OpenApiParameter('low_threshold', int)])
    @action(detail=False, methods=['get'])
    def stock_alerts(self, request):
        low_threshold = safe_int(request.query_params.get('low_threshold'), 10)
        low_stock = Product.objects.filter(is_active=True, stock__gt=0, stock__lte=low_threshold).values('id', 'name', 'barcode', 'stock', 'category__name').order_by('stock')
        out_of_stock = Product.objects.filter(is_active=True, stock=0).values('id', 'name', 'barcode', 'stock', 'category__name').order_by('name')
        return Response({'low_stock': list(low_stock), 'out_of_stock': list(out_of_stock), 'thresholds': {'low_stock': low_threshold}})

    @extend_schema(parameters=[OpenApiParameter('start_date', str), OpenApiParameter('end_date', str)])
    @action(detail=False, methods=['get'])
    def payment_breakdown(self, request):
        payments = Payment.objects.filter(order__status='completed')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date: payments = payments.filter(created_at__date__gte=start_date)
        if end_date: payments = payments.filter(created_at__date__lte=end_date)
        breakdown = payments.values('payment_method').annotate(transaction_count=Count('id'), total_collected=Coalesce(Sum('amount_paid'), 0, output_field=DecimalField()), total_change_given=Coalesce(Sum('change'), 0, output_field=DecimalField())).order_by('-total_collected')
        return Response({'payment_breakdown': list(breakdown)})

    @extend_schema(parameters=[OpenApiParameter('start_date', str), OpenApiParameter('end_date', str)])
    @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
    def cashier_performance(self, request):
        orders = Order.objects.filter(status='completed')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date: orders = orders.filter(created_at__date__gte=start_date)
        if end_date: orders = orders.filter(created_at__date__lte=end_date)
        performance = orders.values('cashier__id', 'cashier__username', 'cashier__first_name', 'cashier__last_name').annotate(total_orders=Count('id'), total_revenue=Coalesce(Sum('grand_total'), 0, output_field=DecimalField()), avg_order_value=Avg('grand_total')).order_by('-total_revenue')
        return Response({'cashier_performance': list(performance)})

    @action(detail=False, methods=['get'])
    def category_breakdown(self, request):
        inventory = Product.objects.filter(is_active=True).values('category__id', 'category__name').annotate(product_count=Count('id'), total_stock=Coalesce(Sum('stock'), 0, output_field=DecimalField()), total_inventory_value=Coalesce(Sum(F('stock') * F('price')), 0, output_field=DecimalField()), low_stock_count=Count('id', filter=Q(stock__lt=10, stock__gt=0)), out_of_stock_count=Count('id', filter=Q(stock=0))).order_by('category__name')
        sales = OrderItem.objects.filter(order__status='completed').values('product__category__id', 'product__category__name').annotate(items_sold=Coalesce(Sum('quantity'), 0, output_field=DecimalField()), revenue=Coalesce(Sum('subtotal'), 0, output_field=DecimalField())).order_by('-revenue')
        return Response({'inventory_by_category': list(inventory), 'sales_by_category': list(sales)})

    @extend_schema(parameters=[OpenApiParameter('limit', int)])
    @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
    def customer_insights(self, request):
        limit = safe_int(request.query_params.get('limit'), 10)
        top_customers = Order.objects.filter(status='completed', customer__isnull=False).values('customer__id', 'customer__name', 'customer__phone').annotate(total_orders=Count('id'), total_spent=Coalesce(Sum('grand_total'), 0, output_field=DecimalField()), avg_spend=Avg('grand_total')).order_by('-total_spent')[:limit]
        return Response({'top_customers': list(top_customers)})