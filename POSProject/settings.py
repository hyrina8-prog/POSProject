import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = 'RENDER' not in os.environ

SECRET_KEY = os.environ.get('SECRET_KEY', 'local-dev-placeholder-never-use-this-in-production-123456789!@#$')

ALLOWED_HOSTS = []

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CORS_ALLOWED_ORIGINS = [
        f"https://{RENDER_EXTERNAL_HOSTNAME}",
    ]
    CSRF_TRUSTED_ORIGINS = [
        f"https://{RENDER_EXTERNAL_HOSTNAME}",
    ]
else:
    ALLOWED_HOSTS.append('127.0.0.1')
    ALLOWED_HOSTS.append('localhost')
    CORS_ALLOW_ALL_ORIGINS = True


# ============================================================
# INSTALLED APPS
# ============================================================

INSTALLED_APPS = [
    # Jazzmin — beautiful admin UI
    'jazzmin',

    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'drf_spectacular',

    # POS app
    'AppAPI',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',        # Must be before CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'POSProject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'POSProject.wsgi.application'


# ============================================================
# DATABASE
# ============================================================

DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",  # Local fallback
        conn_max_age=600,
        conn_health_checks=True,  # Recommended for production
    )
}


# ============================================================
# AUTH
# ============================================================

AUTH_USER_MODEL = 'AppAPI.User'

LOGIN_URL = '/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Tell Django it's secure if the proxy header says it is
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Secure CSRF cookies in production
CSRF_COOKIE_SECURE = not DEBUG


# ============================================================
# SESSION SECURITY
# ============================================================

SESSION_COOKIE_AGE = 8 * 60 * 60  # 28,800 seconds = 8 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG  # True in production, False during dev
SESSION_COOKIE_SAMESITE = 'Lax'


# ============================================================
# REST FRAMEWORK
# ============================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}


# ============================================================
# SWAGGER / OPENAPI (drf-spectacular)
# ============================================================

SPECTACULAR_SETTINGS = {
    'TITLE': 'POS System API',
    'DESCRIPTION': (
        'Complete REST API for a Retail Point-of-Sale system.\n\n'
        '**Roles:**\n'
        '- `admin` — Full access: products, users, reports, stock, orders\n'
        '- `cashier` — POS access: create orders, checkout, view products\n\n'
        '**Authentication:** Token (Bearer) — get token from `/api/login/`'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [{'BearerAuth': []}],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
            }
        }
    },
    'TAGS': [
        {'name': 'Auth',            'description': 'Login and logout'},
        {'name': 'Users',           'description': 'User management (Admin only)'},
        {'name': 'Customers',       'description': 'Customer management'},
        {'name': 'Categories',      'description': 'Product categories'},
        {'name': 'Products',        'description': 'Product catalog and barcode scan'},
        {'name': 'Stock Movements', 'description': 'Stock in/out audit log'},
        {'name': 'Orders',          'description': 'POS orders, cart, checkout, receipt'},
        {'name': 'Order Items',     'description': 'Line items (read-only)'},
        {'name': 'Payments',        'description': 'Payment records (read-only)'},
        {'name': 'Reports',         'description': 'Sales, stock, and analytics reports'},
    ],
}


# ============================================================
# CORS
# ============================================================

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    # In production: whitelist only your own domains
    CORS_ALLOWED_ORIGINS = [
        'https://posproject-my63.onrender.com'
    ]
    CORS_ALLOW_ALL_ORIGINS = False


# ============================================================
# STATIC & MEDIA
# ============================================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'POSProject' / 'static',
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ============================================================
# MISC
# ============================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Phnom_Penh'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

JAZZMIN_SETTINGS = {
    'site_title': 'POS Admin',
    'site_header': 'POS System',
    'site_brand': 'POS',
    'welcome_sign': 'Welcome to POS System Admin',
    'show_sidebar': True,
    'navigation_expanded': True,
    'icons': {
        'AppAPI.User': 'fas fa-users',
        'AppAPI.Customer': 'fas fa-user-tag',
        'AppAPI.Category': 'fas fa-tags',
        'AppAPI.Product': 'fas fa-box',
        'AppAPI.Order': 'fas fa-shopping-cart',
        'AppAPI.OrderItem': 'fas fa-list',
        'AppAPI.Payment': 'fas fa-credit-card',
        'AppAPI.StockMovement': 'fas fa-boxes',
    },
    'order_with_respect_to': [
        'AppAPI.Order', 'AppAPI.OrderItem', 'AppAPI.Payment',
        'AppAPI.Product', 'AppAPI.Category', 'AppAPI.StockMovement',
        'AppAPI.Customer', 'AppAPI.User',
    ],
}

DEFAULT_TAX_RATE = 5.0


# ============================================================
# API BASE URL (THE FIX)
# ============================================================

# Base URL for internal API calls from template views
if 'RENDER' in os.environ:
    # On Render, talk directly to the internal container port.
    # This bypasses the public internet, avoiding deadlocks, latency, and SSL issues!
    API_BASE_URL = f"http://127.0.0.1:{os.environ.get('PORT', 10000)}"
else:
    # Local development
    API_BASE_URL = 'http://127.0.0.1:8000'
