import os

import dj_database_url

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 1. Debug auto-switches: True locally, False on Render
DEBUG = 'RENDER' not in os.environ

# 2. Secret Key: Uses Render's Environment Variable in production, falls back to local random key
SECRET_KEY = os.environ.get('SECRET_KEY', 'local-dev-placeholder-never-use-this-in-production-123456789!@#$')

# 3. Allowed Hosts
ALLOWED_HOSTS = []

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
else:
    ALLOWED_HOSTS.append('127.0.0.1')
    ALLOWED_HOSTS.append('localhost')



# ============================================================
# INSTALLED APPS
# ============================================================

INSTALLED_APPS = [
    # Jazzmin — beautiful admin UI (install: pip install django-jazzmin)
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
        # Fallback to local SQLite if DATABASE_URL environment variable isn't found
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}

# ============================================================
# AUTH
# ============================================================

AUTH_USER_MODEL = 'AppAPI.User'

# ✅ NEW — Tells Django where the login page is
# Used by our @login_required_template decorator and Django's built-in auth
LOGIN_URL = '/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ============================================================
# SESSION SECURITY  ✅ NEW SECTION
# ============================================================

# How long the session lives (default is 1,209,600 = 2 weeks)
# Set to 8 hours for a POS system — cashiers shouldn't stay logged in forever
SESSION_COOKIE_AGE = 8 * 60 * 60  # 28,800 seconds = 8 hours

# Expire session when browser closes (for POS kiosk safety)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Prevent JavaScript from reading the session cookie (XSS protection)
SESSION_COOKIE_HTTPONLY = True

# Only send session cookie over HTTPS in production
SESSION_COOKIE_SECURE = not DEBUG  # True in production, False during dev

# Don't send session cookie in cross-site requests (CSRF protection)
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




# ✅ FIXED — Don't allow ALL origins blindly, even in dev
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    # In production: whitelist only your own domains
    CORS_ALLOWED_ORIGINS = [
        'https://posproject-my63.onrender.com'
    ]
    CORS_ALLOW_ALL_ORIGINS = False

    


# Base URL for internal API calls from template views
# In dev, Django serves both templates and API on the same port
# In production, change this to your actual domain
#API_BASE_URL = 'http://127.0.0.1:8000'

# ⚠️ In production, change to:
API_BASE_URL = 'https://posproject-my63.onrender.com'




STATIC_URL = '/static/'
# This is where Django will collect static files for production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# Enable WhiteNoise compression and caching
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'



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
