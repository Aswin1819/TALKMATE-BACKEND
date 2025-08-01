from django.utils import timezone
from datetime import timedelta
import random
from django.core.mail import send_mail
from django.conf import settings
from .models import OTP,Notification
import cloudinary.uploader
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
    
def generate_and_send_otp(user):
    code = f"{random.randint(100000, 999999)}"
    expires_at = timezone.now() + timedelta(minutes=2)
    
    OTP.objects.create(
        user=user,
        code=code,
        expires_at=expires_at
    )
    subject = "Your TalkMate OTP code"
    html_content = render_to_string("emails/otp_email.html",{
        "user": user,
        "code": code,
        "expires_at": expires_at,
    })
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()



def set_auth_cookies(response, access_token, refresh_token , access_cookie='access_token', refresh_cookie='refresh_token'):
    """
    Utility function to set authentication cookies with proper cross-origin support
    """
    access_exp = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
    refresh_exp = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']

    
    secure = True
    samesite = 'None'
    domain = None  # Or your domain if needed
    
    # print(f"=== COOKIE SETTINGS DEBUG ===")
    # print(f"Secure: {secure}")
    # print(f"SameSite: {samesite}")
    # print(f"Domain: {domain}")
    # print(f"DEBUG mode: {settings.DEBUG}")

    # Set access token cookie
    response.set_cookie(
        key=access_cookie,
        value=access_token,
        max_age=int(access_exp.total_seconds()),
        httponly=True,
        secure=secure,
        samesite=samesite,
        path='/',
        domain=domain,
    )
    
    # Set refresh token cookie
    response.set_cookie(
        key=refresh_cookie,
        value=refresh_token,
        max_age=int(refresh_exp.total_seconds()),
        httponly=True,
        secure=secure,
        samesite=samesite,
        path='/',
        domain=domain,
    )

    # print(f"Cookies set - {access_cookie}: {access_token[:20]}..., {refresh_cookie}: {refresh_token[:20]}...")


def clear_auth_cookies(response):
    """Utility function to clear authentication cookies"""

    secure = True
    samesite = 'None'
    domain = None  # Or your domain if needed
    
    # print(f"=== CLEARING COOKIES DEBUG ===")
    # print(f"Secure: {secure}")
    # print(f"SameSite: {samesite}")
    # print(f"Domain: {domain}")
    
    response.delete_cookie(
        'access_token',
        path='/',
        samesite=samesite,
        domain=domain
    )
    response.delete_cookie(
        'refresh_token',
        path='/',
        samesite=samesite,
        domain=domain
    )



    
def upload_avatar_to_cloudinary(file, folder='avatars'):
    """
    Uploads an avatar image to Cloudinary and returns the URL.
    """
    print("=== upload_avatar_to_cloudinary called ===")
    if not file:
        print("No file provided to upload_avatar_to_cloudinary.")
        return None

    # print(f"Uploading file: {file} to Cloudinary in folder: {folder}")
    try:
        response = cloudinary.uploader.upload(
            file,
            folder=folder,
            allowed_formats=['jpg', 'jpeg', 'png'],
            overwrite=True,
            resource_type='image',
            transformation=[
                {'width': 200, 'height': 200, 'crop': 'fill', 'gravity': 'face'}
            ]
        )
        # print("Cloudinary upload response:", response)
        url = response.get('secure_url')
        if url:
            print("Successfully uploaded to Cloudinary. URL:")
        else:
            print("Upload to Cloudinary succeeded but no URL returned.")
        return url
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        return None


def send_notification(user, notif_type, title, message, link=None):
    Notification.objects.create(
        user=user,
        type=notif_type,
        title=title,
        message=message,
        link=link
    )


def send_notification_to_user(user_id, notification_data):
    """
    Send real-time notification to a specific user via WebSocket
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            'type': 'notification_message',
            'notification': notification_data
        }
    )

def send_notification_count_update(user_id, count):
    """
    Send notification count update to a specific user
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            'type': 'notification_count_update',
            'count': count
        }
    )

def send_chat_message_to_user(user_id, message_data):
    """
    Send real-time chat message to a specific user via WebSocket
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            'type': 'chat_message',
            'message': message_data['message'],
            'sender_id': message_data['sender_id'],
            'sender_username': message_data['sender_username']
        }
    )