from celery import shared_task
from .models import CustomUser
from .utils import generate_and_send_otp
from django.shortcuts import get_object_or_404

@shared_task
def send_otp_email_task(user_id):
    user = get_object_or_404(CustomUser,id=user_id)
    generate_and_send_otp(user)

