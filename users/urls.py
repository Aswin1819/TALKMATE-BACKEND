# users/urls.py

from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import *
 

router = DefaultRouter()
# router.register('profiles', UserProfileViewSet, basename='userprofile')
router.register('languages', LanguageViewSet, basename='language')
router.register('friendships', FriendshipViewSet, basename='friendship')
router.register('subscription', SubscriptionPlanViewSet, basename='subscription')



urlpatterns = [
    path('',include(router.urls)),
    path('login/', CustomLoginView.as_view(), name='custom_token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('google-login/', GoogleLoginView.as_view(), name='google_login'),
    path('register/',RegisterView.as_view(),name='register'),
    path('verify-otp/',OTPVerifyView.as_view(),name='verify_otp'),
    path('resend-otp/',ResendOTPView.as_view(),name='resend-otp'),
    path('current-user/',CurrentUserView.as_view(),name='current-user'),
    path('logout/',LogoutView.as_view(),name='logout'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('verify-password-reset-otp/', PasswordResetOTPVerifyView.as_view(), name='verify-password-reset-otp'),
    path('resend-password-reset-otp/', PasswordResetResendOTPView.as_view(), name='resend-password-reset-otp'),
    path('profile/', CurrentUserProfileView.as_view(), name='current-user-profile'),
    path('profile/update/', UpdateUserProfileView.as_view(), name='update-profile'),
    path('proficiency-choices/', ProficiencyChoicesView.as_view(), name='proficiency-choices'),
    path('get-access-token/', AccessTokenView.as_view(), name='get=access-token'),
    
    path('settings/', UserSettingsView.as_view(), name='user-settings'),
    path('settings/delete-account/', DeleteAccountView.as_view(), name='delete-account'),
    path('settings/change-password/', ChangePasswordView.as_view(), name='change-password'),
    #languages/
    path('notifications/', NotificationListView.as_view(), name='user-notifications'),
    #paytments
    path('payment/create-order/', CreateRazorpayOrder.as_view()),
    path('payment/verify/', VerifyRazorpayPayment.as_view()),

    # other user routes...
]
