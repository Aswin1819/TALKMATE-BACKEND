# users/urls.py

from django.urls import path,include
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.routers import DefaultRouter
from .views import (
    CustomLoginView,
    RegisterView,
    UserProfileViewSet,
    LanguageViewSet,
    FriendshipViewSet,
    OTPVerifyVeiw,
    LogoutView,
    ResendOTPView
)

router = DefaultRouter()
router.register('profiles', UserProfileViewSet, basename='userprofile')
router.register('languages', LanguageViewSet, basename='language')
router.register('friendships', FriendshipViewSet, basename='friendship')



urlpatterns = [
    path('',include(router.urls)),
    path('login/', CustomLoginView.as_view(), name='custom_token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/',RegisterView.as_view(),name='register'),
    path('verify-otp/',OTPVerifyVeiw.as_view(),name='verify_otp'),
    path('resend-otp/',ResendOTPView.as_view(),name='resend-otp'),
    path('logout/',LogoutView.as_view(),name='logout'),
    
    
    # other user routes...
]
