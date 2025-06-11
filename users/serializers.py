from rest_framework import serializers
from .models import CustomUser,UserProfile,Language,OTP,Friendship
from django.utils.timesince import timesince
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import AuthenticationFailed
import re


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'is_verified', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def validate_username(self,value):
            if not re.match(r'^[A-Za-z]+( [A-Za-z]+)*$', value):
                raise serializers.ValidationError("Username must contain only letters and spaces between words.")
            return value
    
    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

        
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['email'] = user.email
        token['username'] = user.username
        token['user_id'] = user.id
        token['is_verified'] = user.is_verified
        return token

    def validate(self, attrs):
        try:
            data = super().validate(attrs)
        except Exception as e:
            raise AuthenticationFailed("Invalid credentials provided.")

        # Additional user validation
        if not self.user.is_verified:
            raise AuthenticationFailed("Email is not verified. Please verify your account.")
        
        if not self.user.is_active:
            raise AuthenticationFailed("Your account has been blocked by the admin.")

        # Add user data to response
        data.update({
            'user': {
                'user_id': self.user.id,
                'username': self.user.username,
                'email': self.user.email,
                'is_verified': self.user.is_verified,
            }
        })

        return data
    
class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id','name','code']
        
class UserProfileSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)
    native_language = LanguageSerializer(read_only=True)
    learning_languages = LanguageSerializer(many=True,read_only=True)
    follwers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    last_seen_display = serializers.SerializerMethodField()
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'unique_id', 'avatar', 'bio', 'native_language',
            'learning_languages', 'status', 'is_premium', 'xp', 'level', 'streak',
            'total_speak_time', 'total_rooms_joined', 'is_online', 'last_seen', 
            'last_seen_display', 'following', 'followers_count', 'following_count'
        ]
    def get_followers_count(self,obj):
        return obj.follwers_count()
    
    def get_following_count(self,obj):
        return obj.following_count()
    
    def get_last_seen_display(self,obj):
        if obj.last_seen:
            return timesince(obj.last_seen) + "ago"
        return "Never"

class OTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTP
        fields = ['id','user','code','created_at','expires_at']
        read_only_fields = ['created_at']
        
        
class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")

        if user.is_verified:
            raise serializers.ValidationError("User is already verified.")

        self.context['user'] = user
        return value
        
        


class FriendshipSerializer(serializers.ModelSerializer):
    from_user_email = serializers.EmailField(source='from_user.email', read_only=True)
    to_user_email = serializers.EmailField(source='to_user.email', read_only=True)

    class Meta:
        model = Friendship
        fields = [
            'id', 'from_user', 'from_user_email',
            'to_user', 'to_user_email',
            'status', 'created_at'
        ]
        read_only_fields = ['created_at']

    
