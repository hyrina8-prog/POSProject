"""
URL configuration for POSProject project.

The `urlpatterns` list routes URLs to views.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)

# CHANGED: Import your dedicated frontend views here!



urlpatterns = [

    # =========================
    # ADMIN
    # =========================
    path('admin/', admin.site.urls),

    # =========================
    # TEMPLATE ROUTES
    # =========================
    path('', include('AppAPI.template_urls')),

    # =========================
    # API ROUTES
    # =========================
    path('api/', include('AppAPI.urls')),

    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # =========================
    # API DOCUMENTATION
    # =========================
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# MEDIA FILES
urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)