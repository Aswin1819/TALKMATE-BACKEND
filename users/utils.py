from django.utils import timezone
from datetime import timedelta
import random
from django.core.mail import send_mail
from django.conf import settings
from .models import OTP  # Adjust import path

def generate_and_send_otp(user):
    code = f"{random.randint(100000, 999999)}"
    expires_at = timezone.now() + timedelta(minutes=2)
    
    OTP.objects.create(
        user=user,
        code=code,
        expires_at=expires_at
    )

    send_mail(
        subject="Your TalkMate OTP Code",
        message=f"Your OTP code is {code}. It will expire in 2 minutes.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    

def set_auth_cookies(response, access_token, refresh_token):
    access_exp = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
    refresh_exp = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']

    is_secure = getattr(settings, 'AUTH_COOKIE_SECURE', True)
    same_site = getattr(settings, 'AUTH_COOKIE_SAMESITE', 'Lax')

    response.set_cookie(
        key='access_token',
        value=access_token,
        max_age=int(access_exp.total_seconds()),
        httponly=True,
        secure=is_secure,
        samesite=same_site
    )
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        max_age=int(refresh_exp.total_seconds()),
        httponly=True,
        secure=is_secure,
        samesite=same_site
    )

