from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .models import *
from .serializers import *
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from .utils import generate_and_send_otp,set_auth_cookies

class RegisterView(APIView):
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
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response({'detail': 'Invalid credentials or user inactive'}, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.user
        if not user.is_verified:
            return Response({'detail': 'Email is not verified. Please verify to log in.'}, status=status.HTTP_403_FORBIDDEN)

        access_token = serializer.validated_data.get('access')
        refresh_token = serializer.validated_data.get('refresh')

        response_data = {
            "user": {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "is_verified": user.is_verified,
            }
        }
        response = Response(response_data, status=status.HTTP_200_OK)

        set_auth_cookies(response, access_token, refresh_token)

        return response
        
    
    


class UserProfileViewSet(ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    
class LanguageViewSet(ModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    
class FriendshipViewSet(ModelViewSet):
    queryset = Friendship.objects.all()
    serializer_class = FriendshipSerializer
    
class OTPVerifyVeiw(APIView):
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
            
            generate_and_send_otp(user)  # ✅ reuse the helper function

            return Response({"message": "OTP sent successfully."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
        
class LogoutView(APIView):
    def post(self, request):
        response = Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response

