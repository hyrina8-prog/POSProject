# template_views.py
import json
import logging

from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings

from .api_helper import api_call
from .decorators import login_required_template, admin_required_template

logger = logging.getLogger(__name__)


# =========================
# AUTH
# =========================

def login_page(request):
    if request.method == 'POST':
        username_input = request.POST.get('username', '')
        password_input = request.POST.get('password', '')

        response = api_call(
            'POST',
            '/api/login/',
            data={'username': username_input, 'password': password_input}
        )

        if response is None:
            messages.error(request, 'Service unavailable. Please try again later.')
            return render(request, 'login.html')

        if response.status_code == 200:
            data = response.json()

            request.session['token']    = data['token']
            request.session['user_id']  = data['user_id']
            request.session['username'] = data['username']
            request.session['role']     = data.get('role', 'staff')

            request.session.cycle_key()

            if data.get('role') == 'admin':
                return redirect('template_dashboard')
            else:
                return redirect('template_pos')
        else:
            logger.warning(
                f"Login failed for '{username_input}': "
                f"{response.status_code} - {response.text}"
            )
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')


def logout_page(request):
    token = request.session.get('token')
    if token:
        api_call('POST', '/api/logout/', token=token)
    request.session.flush()
    return redirect('template_login')


# =========================
# SHARED CONTEXT HELPER
# =========================

def _session_context(request):
    """
    Builds the context dict that every protected template needs.
    Injects session data + API URL so JavaScript can call the API.
    """
    return {
        'token':        request.session.get('token', ''),
        'username':     request.session.get('username', ''),
        'role':         request.session.get('role', ''),
        'user_id':      request.session.get('user_id', ''),
        'api_base_url': getattr(settings, 'API_BASE_URL', 'http://127.0.0.1:8000'),
    }


# =========================
# ADMIN PAGES
# =========================

@admin_required_template
def dashboard_page(request):
    """Admin-only dashboard with stats, recent orders, and low stock."""
    context = _session_context(request)
    return render(request, 'dashboard.html', context)


@login_required_template
def products_page(request):
    token = request.session.get('token')
    
    # 1. Fetch Products
    prod_resp = api_call('GET', '/api/products/', token=token)

    products = []
    if prod_resp and prod_resp.status_code == 200:
        data = prod_resp.json()
        products = data.get('results', data) if isinstance(data, dict) else data
    elif prod_resp is None:
        messages.error(request, 'Could not reach the products service.')
    elif prod_resp.status_code == 401 or prod_resp.status_code == 403:
        messages.error(request, 'Authentication failed. Please log out and log back in.')
    else:
        messages.error(request, f'Failed to load products. API Error: {prod_resp.status_code}')

    # 2. Fetch Categories
    cat_resp = api_call('GET', '/api/categories/', token=token)
    categories = []
    if cat_resp and cat_resp.status_code == 200:
        data = cat_resp.json()
        categories = data.get('results', data) if isinstance(data, dict) else data

    # ✅ FIXED INDENTATION: Context must be outside the if blocks!
    context = {
        'products_data': products,
        'categories_data': categories,
        **_session_context(request),
    }
    
    return render(request, 'products.html', context)


# =========================
# CATEGORIES PAGE ✅ UPDATED
# =========================

@login_required_template
def categories_page(request):
    token = request.session.get('token')
    
    cat_resp = api_call('GET', '/api/categories/', token=token)
    
    categories = []
    if cat_resp and cat_resp.status_code == 200:
        data = cat_resp.json()
        categories = data.get('results', data) if isinstance(data, dict) else data
    elif cat_resp is None:
        messages.error(request, 'Could not reach the categories service.')
    else:
        messages.error(request, 'Failed to load categories.')

    context = {
        'categories_data': categories,
        'page_title': 'Categories',
        **_session_context(request),
    }
    
    return render(request, 'categories.html', context)


# =========================
# CASHIER PAGE
# =========================

@login_required_template
def pos_page(request):
    token = request.session.get('token')

    prod_resp = api_call('GET', '/api/products/', token=token)
    cat_resp  = api_call('GET', '/api/categories/', token=token)

    if prod_resp is None:
        prod_resp = type('FakeResp', (), {'status_code': 503, 'json': lambda self: []})()
    if cat_resp is None:
        cat_resp = type('FakeResp', (), {'status_code': 503, 'json': lambda self: []})()

    products  = prod_resp.json()  if prod_resp.status_code == 200 else []
    categories = cat_resp.json()  if cat_resp.status_code == 200 else []

    context = {
        'products_json':  json.dumps(products),
        'categories_json': json.dumps(categories),
        'default_tax_rate': getattr(settings, 'DEFAULT_TAX_RATE', 0),
        **_session_context(request),
    }
    return render(request, 'pos.html', context)


# =========================
# STUB PAGES (coming soon)
# =========================

@login_required_template
def customers_page(request):
    token = request.session.get('token')
    
    cust_resp = api_call('GET', '/api/customers/', token=token)
    
    customers = []
    if cust_resp and cust_resp.status_code == 200:
        data = cust_resp.json()
        customers = data.get('results', data) if isinstance(data, dict) else data
    elif cust_resp is None:
        messages.error(request, 'Could not reach the customers service.')
    else:
        messages.error(request, 'Failed to load customers.')

    context = {
        'customers_data': customers,
        'page_title': 'Customers',
        **_session_context(request),
    }
    
    return render(request, 'customers.html', context)


@login_required_template
def stock_page(request):
    token = request.session.get('token')
    
    mov_resp = api_call('GET', '/api/stock-movements/', token=token)
    prod_resp = api_call('GET', '/api/products/', token=token)
    
    movements = []
    if mov_resp and mov_resp.status_code == 200:
        data = mov_resp.json()
        movements = data.get('results', data) if isinstance(data, dict) else data

    products = []
    if prod_resp and prod_resp.status_code == 200:
        data = prod_resp.json()
        products = data.get('results', data) if isinstance(data, dict) else data

    context = {
        'stock_data': movements,
        'products_data': products,
        'page_title': 'Stock Management',
        **_session_context(request),
    }
    
    return render(request, 'stock.html', context)


@admin_required_template
def reports_page(request):
    context = _session_context(request)
    context['page_title'] = 'Reports'
    return render(request, 'reports.html', context)


@admin_required_template
def users_page(request):
    token = request.session.get('token')
    
    user_resp = api_call('GET', '/api/users/', token=token)
    
    users = []
    if user_resp and user_resp.status_code == 200:
        data = user_resp.json()
        users = data.get('results', data) if isinstance(data, dict) else data
    elif user_resp is None:
        messages.error(request, 'Could not reach the users service.')
    else:
        messages.error(request, 'Failed to load users.')

    context = {
        'users_data': users,
        'page_title': 'Users',
        **_session_context(request),
    }
    
    return render(request, 'users.html', context)