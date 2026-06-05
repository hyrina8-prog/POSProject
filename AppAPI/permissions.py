"""
Custom Permission Classes for POS System
==========================================

Role Hierarchy:
- ADMIN    : Full access — manage products, users, stock, reports, orders
- CASHIER  : POS operations — create orders, process payments, view products

Usage in views:
    from .permissions import IsAdmin, IsCashier, IsAdminOrCashier

    class OrderViewSet(viewsets.ModelViewSet):
        def get_permissions(self):
            if self.action in ['create', 'checkout']:
                permission_classes = [IsAdminOrCashier]
            elif self.action in ['destroy']:
                permission_classes = [IsAdmin]
            else:
                permission_classes = [IsAuthenticated]
            return [permission() for permission in permission_classes]
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    """Allows access only to users with role='admin'."""
    message = "This action requires Admin privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsCashier(BasePermission):
    """Allows access only to users with role='cashier'."""
    message = "This action requires Cashier privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'cashier'
        )


class IsAdminOrCashier(BasePermission):
    """Allows access to Admin or Cashier users."""
    message = "This action requires Admin or Cashier privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'cashier']
        )


class IsAdminOrReadOnly(BasePermission):
    """
    Allows read access to any authenticated user.
    Write access restricted to Admin only.
    Used for: Categories, Products (Admin manages, Cashier reads).
    """
    message = "Write access requires Admin privileges."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role == 'admin'


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level: allow access to the owner of the resource or an admin.
    Used for: Users viewing/editing their own profile.
    """
    message = "You can only access your own data."

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        # Support both User objects and objects with a cashier/user FK
        if hasattr(obj, 'cashier'):
            return obj.cashier == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return obj == request.user
