# decorators.py
import functools
from django.shortcuts import redirect


def login_required_template(view_func):
    """
    Checks if a token exists in the session.
    If not, kicks the user back to the login page.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'token' not in request.session:
            return redirect('template_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required_template(view_func):
    """
    Checks if the user has admin role.
    If not, redirects to the POS page.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'token' not in request.session:
            return redirect('template_login')
        if request.session.get('role') != 'admin':
            return redirect('template_pos')
        return view_func(request, *args, **kwargs)
    return wrapper