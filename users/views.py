import razorpay
from .models import *
from .serializers import *
from decouple import config
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from google.oauth2 import id_token
from rest_framework.views import APIView
from google.auth.transport import requests
from decimal import Decimal, ROUND_HALF_UP
from rest_framework import status,viewsets
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .utils import generate_and_send_otp,set_auth_cookies,clear_auth_cookies
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView

User = get_user_model()

  
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        id_token_str = request.data.get('id_token')

        if not id_token_str:
            return Response({'error': 'No token provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID')
            idinfo = id_token.verify_oauth2_token(id_token_str, requests.Request(), GOOGLE_CLIENT_ID)

            if idinfo['aud'] != GOOGLE_CLIENT_ID:
                raise AuthenticationFailed('Invalid audience')

            email = idinfo.get('email')
            name = idinfo.get('given_name')[:5] if idinfo.get('given_name') else 'User'

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': name,
                    'is_active': True,
                    'is_verified': True,
                    'is_google_login':True,
                }
            )
            
            if not created and not user.is_google_login:
                user.is_google_login = True
                user.save(update_fields=['is_google_login'])

            # Use serializer to generate token and data
            serializer = GoogleLoginSerializer(data={}, context={'user': user})
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            access_token = validated_data['access']
            refresh_token = validated_data['refresh']

            response = Response({
                'message': 'Login successful',
                'user': validated_data['user'],
                'debug': {
                    'access_preview': access_token[:20] + "...",
                    'refresh_preview': refresh_token[:20] + "...",
                } if settings.DEBUG else {}
            })

            set_auth_cookies(response, access_token, refresh_token)
            return response

        except ValueError as e:
            return Response({'error': f'Invalid token: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except AuthenticationFailed as e:
            return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


















class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    @transaction.atomic
    def post(self, request):
        data = request.data.copy()
        password = data.get('password')

        try:
            validate_password(password)
        except Exception as e:
            return Response({'password': list(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CustomUserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            
            generate_and_send_otp(user)

            user_data = serializer.data
            user_data.pop('password', None)

            return Response({
                'message': 'OTP successfully sent to your email',
                'user': user_data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class CustomLoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        print("=== CustomLoginView POST called ===")
        print("Request data:", request.data)
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
            print("Serializer valid. User:", serializer.user)
            print("Serializer data:", serializer.validated_data)
        except AuthenticationFailed as e:
            return Response(
                {'detail': str(e)}, 
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            print("Serializer error:", str(e))
            return Response(
                {'detail': 'Invalid credentials or user inactive'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get tokens and user data
        validated_data = serializer.validated_data
        access_token = validated_data.get('access')
        refresh_token = validated_data.get('refresh')
        user_data = validated_data.get('user')
        
        
        # Create response
        response_data = {
            'message': 'Login successful',
            'user': user_data,
            'debug': {
                'cookies_set': True,
                'access_token_preview': access_token[:20] + '...' if access_token else None,
            } if settings.DEBUG else {}
        }
        
        response = Response(response_data, status=status.HTTP_200_OK)
        
        # Set authentication cookies
        set_auth_cookies(response, access_token,
                        refresh_token,
                        access_cookie='access_token',
                        refresh_cookie='refresh_token'
                    )

        return response
        
    


    
class CustomTokenRefreshView(TokenRefreshView):
    """Custom token refresh view that works with cookies"""
    
    def post(self, request, *args, **kwargs):
        # Debug prints
        print("=== TOKEN REFRESH DEBUG ===")
        print(f"Request method: {request.method}")
        print(f"Request data: {request.data}")
        print(f"Request cookies: {dict(request.COOKIES)}")
        print(f"Content-Type: {request.content_type}")
        
        # Try to get refresh token from cookie if not in request body
        if 'refresh' not in request.data:
            refresh_token = request.COOKIES.get('refresh_token')
            print(f"Refresh token from cookie: {refresh_token}")
            
            if refresh_token:
                if hasattr(request, '_mutable'):
                    request.data._mutable = True
                    
                data = request.data.copy()
                data['refresh'] = refresh_token
                
                # Update request data
                request._full_data = data
                print(f"Updated request data: {data}")
            else:
                print("No refresh token found in cookies")
                return Response(
                    {'detail': 'No refresh token found'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            response = super().post(request, *args, **kwargs)
            print(f"Super response status: {response.status_code}")
            print(f"Super response data: {response.data}")
            
            if response.status_code == 200:
                # Get new tokens
                access_token = response.data.get('access')
                refresh_token = response.data.get('refresh')  # If rotation is enabled
                
                print(f"New access token: {access_token[:20]}..." if access_token else "No access token")
                print(f"New refresh token: {refresh_token[:20]}..." if refresh_token else "No refresh token")
                
                # Update cookies
                if refresh_token:  # If refresh token rotation is enabled
                    set_auth_cookies(response, access_token, refresh_token)
                else:
                    # Only update access token cookie
                    access_exp = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
                    secure = False if settings.DEBUG else getattr(settings, 'AUTH_COOKIE_SECURE', True)
                    samesite = 'None' if settings.DEBUG else getattr(settings, 'AUTH_COOKIE_SAMESITE', 'None')
                    domain = getattr(settings, 'AUTH_COOKIE_DOMAIN', None)
                    
                    response.set_cookie(
                        key='access_token',
                        value=access_token,
                        max_age=int(access_exp.total_seconds()),
                        httponly=True,
                        secure=secure,
                        samesite=samesite,
                        path='/',
                        domain=domain,
                    )
                
                # Clean response data
                response.data = {
                    'message': 'Token refreshed successfully',
                    'debug': {
                        'cookies_updated': True,
                    } if settings.DEBUG else {}
                }
            
            return response
            
        except (TokenError, InvalidToken) as e:
            print(f"Token error: {e}")
            # Clear invalid cookies
            response = Response(
                {'detail': f'Invalid or expired refresh token: {str(e)}'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
            clear_auth_cookies(response)
            return response
        except Exception as e:
            print(f"Unexpected error: {e}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'detail': f'Unexpected error: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    



class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self,request):
        serializer = CustomUserSerializer(request.user)
        print("Current user serializer data:", serializer.data)
        return Response({'user':serializer.data})
        
    





# class UserProfileViewSet(ModelViewSet):
#     queryset = UserProfile.objects.all()
#     serializer_class = UserProfileSerializer
    
class LanguageViewSet(ModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    
    
    
class FriendshipViewSet(ModelViewSet):
    queryset = Friendship.objects.all()
    serializer_class = FriendshipSerializer

class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    def post(self,request):
        email = request.data.get('email')
        code = request.data.get('code')
        print(f"Received email:{email}, code:{code}")
        try:
            user = CustomUser.objects.get(email=email)
            print(f"found user:{user}")
            otp_obj = OTP.objects.filter(user=user,code=code,is_used=False).latest('created_at')
            print("found otp_obj:{otp_obj}")
            if otp_obj.is_expired():
                print("otp is expired")
                return Response({'error':'OTP expired'},status=400)
            otp_obj.is_used = True
            otp_obj.save()
            user.is_verified = True
            user.save()
            print("otp verified")
            return Response({'message':'OTP verified Successfully'})
        except CustomUser.DoesNotExist:
            print("User not found")
            return Response({'error':'User not found'},status=400)  
        except OTP.DoesNotExist:
            print("invalid otp")
            return Response({'error':'Invalid OTP'},status=400)
        
        
class ResendOTPView(APIView):
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.context['user']
            
            generate_and_send_otp(user)  

            return Response({"message": "OTP sent successfully."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
        
class LogoutView(TokenRefreshView):
    """Custom logout view that clears cookies"""
    
    def post(self, request, *args, **kwargs):
        response = Response(
            {'message': 'Logged out successfully'}, 
            status=status.HTTP_200_OK
        )
 
        clear_auth_cookies(response)
        
        return response


class PasswordResetOTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetOTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            otp_obj = serializer.validated_data['otp_obj']
            user = serializer.validated_data['user']
            otp_obj.is_used = True
            otp_obj.save()
            # Optionally, set a flag on user to allow password reset
            return Response({'message': 'OTP verified successfully. You can now reset your password.'})
        return Response({'message':serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.context['user']
            generate_and_send_otp(user)
            return Response({'message': 'OTP resent successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def put(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Password reset successful.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class CurrentUserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self,request):
        try:
            profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            return Response({'error':'Profile not found'},status=status.HTTP_404_NOT_FOUND)
        serializers = UserProfileSerializer(profile)
        # print("Serializers data:", serializers.data)
        return Response(serializers.data) # removed the wrapping of profile key.


class UpdateUserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request):
        try:
            profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)
        serializer = UserProfileUpdateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UserProfileSerializer(profile).data)
        return Response(serializer.errors, status=400)
    
    def put(self, request):
        print("=== PUT /profile/update/ called ===")
        print("Request user:", request.user)
        print("Request user authenticated:", request.user.is_authenticated)
        print("Request content-type:", request.content_type)
        print("Request data:", request.data)
        print("Request FILES:", request.FILES)
        try:
            profile = request.user.userprofile
            print("Found user profile:", profile)
        except UserProfile.DoesNotExist:
            print("UserProfile not found for user:", request.user)
            return Response({'error': 'Profile not found'}, status=404)
        serializer = UserProfileUpdateSerializer(profile, data=request.data, partial=True)
        print("Serializer initialized. Is valid?", serializer.is_valid())
        if not serializer.is_valid():
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=400)
        serializer.save()
        print("Profile updated successfully. New avatar URL:", profile.avatar)
        return Response({'profile': UserProfileSerializer(profile).data})
        
class ProficiencyChoicesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        choices = [
            {'value': choice[0], 'label': choice[1]}
            for choice in UserLanguage.Proficiency.choices
        ]
        return Response(choices, status=status.HTTP_200_OK)



class UserSettingsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user's settings"""
        try:
            user_settings = UserSettings.objects.get(user=request.user)
        except UserSettings.DoesNotExist:
            # Create default settings if they don't exist
            user_settings = UserSettings.objects.create(user=request.user)
        
        serializer = UserSettingsSerializer(user_settings)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request):
        """Update user settings"""
        try:
            user_settings = UserSettings.objects.get(user=request.user)
        except UserSettings.DoesNotExist:
            user_settings = UserSettings.objects.create(user=request.user)
        
        serializer = UserSettingsSerializer(user_settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Mark user account as deleted (soft delete)"""
        user = request.user
        
        # Mark user settings as deleted
        try:
            user_settings = UserSettings.objects.get(user=user)
            user_settings.is_deleted = True
            user_settings.save()
        except UserSettings.DoesNotExist:
            pass

        user.is_active = False
        user.save()
        
        return Response(
            {'message': 'Account deleted successfully'}, 
            status=status.HTTP_200_OK
        )

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Change user password"""
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'Password changed successfully'}, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class AccessTokenView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        token = request.COOKIES.get('access_token')
        return Response({'token':token})

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID,settings.RAZORPAY_KEY_SECRET))

class CreateRazorpayOrder(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self,request):
        plan_id = request.data.get('plan_id')
        plan = get_object_or_404(SubscriptionPlan,id=plan_id)
        # amount = int(plan.price * 100) 
        discount = Decimal(0)
        now = timezone.now()
        user = request.user

        existing_subscription = getattr(user, 'subscription', None)
        if existing_subscription and existing_subscription.plan:
            current_plan = existing_subscription.plan
            current_end = existing_subscription.end_date

            if plan.price > current_plan.price:
                remaining_days = max((current_end - now).days, 0)
                daily_rate = current_plan.price / Decimal(current_plan.duration_days)
                discount = (daily_rate * remaining_days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Final amount to charge (after discount)
        final_price = max(plan.price - discount, 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        amount = int(final_price * 100)  # Razorpay expects amount in paise
        
        razorpay_order = client.order.create({
            "amount": amount,
            "currency": "INR",
            "payment_capture": 1
        })

        return Response({
        "order_id": razorpay_order['id'],
        "amount": amount,
        "currency": "INR",
        "key": settings.RAZORPAY_KEY_ID,
        "plan_id": plan.id,
        "final_price": str(final_price),
        "discount_applied": str(discount),
    })


class VerifyRazorpayPayment(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data

        try:
            # Step 1: Verify Razorpay Signature
            client.utility.verify_payment_signature({
                "razorpay_order_id": data["razorpay_order_id"],
                "razorpay_payment_id": data["razorpay_payment_id"],
                "razorpay_signature": data["razorpay_signature"]
            })

            new_plan = get_object_or_404(SubscriptionPlan, id=data['plan_id'])
            now = timezone.now()
            end_date = now + timedelta(days=new_plan.duration_days)

            existing_subscription = getattr(request.user, 'subscription', None)
            discount = Decimal(0)

            if existing_subscription and existing_subscription.plan:
                current_plan = existing_subscription.plan
                current_end = existing_subscription.end_date

                # Only apply proration if new plan is more expensive
                if new_plan.price > current_plan.price:
                    remaining_days = max((current_end - now).days, 0)
                    daily_rate = current_plan.price / Decimal(current_plan.duration_days)
                    discount = (daily_rate * remaining_days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
                UserSubscriptionHistory.objects.create(
                    user=request.user,
                    plan=current_plan,
                    start_date=existing_subscription.start_date,
                    end_date=now,
                    payment_id=existing_subscription.payment_id,
                    payment_status=existing_subscription.payment_status
                )
            
                    

            # Final charge after applying discount
            final_price = max(new_plan.price - discount, 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # Update/Create new subscription
            UserSubscription.objects.update_or_create(
                user=request.user,
                defaults={
                    "plan": new_plan,
                    "start_date": now,
                    "end_date": end_date,
                    "is_active": True,
                    "payment_id": data["razorpay_payment_id"],
                    "payment_status": "paid"
                }
            )

            # Update is_premium flag
            profile = get_object_or_404(UserProfile, user=request.user)
            profile.is_premium = new_plan.price > 0
            profile.save()

            return Response({
                "message": "Subscription upgraded",
                "charged": str(final_price),
                "discount_applied": str(discount),
            })

        except razorpay.errors.SignatureVerificationError:
            return Response({"error": "Payment verification failed"}, status=status.HTTP_400_BAD_REQUEST)
        

class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]
    
class UserSubscriptionHistoryView(APIView):
    perimission_classes= [IsAuthenticated]
    
    def get(self,request):
        history = UserSubscriptionHistory.objects.filter(user=request.user).order_by('-start_date')
        serializer = UserSubscriptionHistorySerializer(history,many=True)
        return Response(serializer.data)

    