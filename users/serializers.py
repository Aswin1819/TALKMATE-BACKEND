from rest_framework import serializers
from .models import *
from django.utils.timesince import timesince
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .utils import upload_avatar_to_cloudinary
from rest_framework.exceptions import AuthenticationFailed
import re
from django.db.models import Q
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken



class CustomUserSerializer(serializers.ModelSerializer):
    profile_summary = serializers.SerializerMethodField()
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'is_verified', 'password', 'profile_summary']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def get_profile_summary(self, obj):
        try:
            profile = obj.userprofile
            friends_count = Friendship.objects.filter(
                (Q(from_user=obj) | Q(to_user=obj)) & Q(status='accepted')
            ).count()
            return {
                'avatar': profile.avatar,
                'level': profile.level,
                'followers': profile.followers.count(),
                'following': profile.following.count(),
                'friends': friends_count,
            }
        except UserProfile.DoesNotExist:
            return None

    def validate_username(self,value):
            if not re.match(r'^[A-Za-z]+( [A-Za-z]+)*$', value):
                raise serializers.ValidationError("Username must contain only letters and spaces between words.")
            return value
    
    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class GoogleLoginSerializer(serializers.Serializer):
    user = serializers.HiddenField(default=None)
    
    def validate(self,attrs):
        user = self.context['user']
        
        if not user.is_active:
            raise serializers.ValidationError('Your account has been deactivated')
        if not user.is_verified:
            raise serializers.ValidationError('Your email is not verifeid')
        if user.is_superuser:
            raise serializers.ValidationError('Superusers cannot log in this way')
        
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        avatar = None
        followers_count = 0
        following_count = 0
        friends_count = 0
        
        try:
            profile=user.userprofile
            avatar=profile.avatar
            followers_count=profile.followers.count()
            following_count=profile.following.count()
            friends_count=Friendship.objects.filter(
                (Q(from_user=user) | Q(to_user=user)) & Q(status='accepted')
            ).count()
        except UserProfile.DoesNotExist:
            pass
        
        return {
            'access':access_token,
            'refresh':refresh_token,
            'user': {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'is_verified': user.is_verified,
                'avatar': avatar,
                'followers_count': followers_count,
                'following_count': following_count,
                'friends_count': friends_count,
            }
        }
        




        
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
        
        if self.user.is_superuser:
            raise AuthenticationFailed("Superusers cannot log in through this endpoint.")

        # Get avatar from UserProfile
        avatar = None
        followers_count = 0
        following_count = 0
        friends_count = 0
        try:
            profile = self.user.userprofile
            avatar = profile.avatar
            followers_count = profile.followers.count()
            following_count = profile.following.count()
            friends_count = Friendship.objects.filter(
                (Q(from_user=self.user) | Q(to_user=self.user)) & Q(status='accepted')
            ).count()
        except UserProfile.DoesNotExist:
            print("UserProfile does not exist for user:", self.user.id)

        data.update({
            'user': {
                'user_id': self.user.id,
                'username': self.user.username,
                'email': self.user.email,
                'is_verified': self.user.is_verified,
                'avatar': avatar,
                'followers_count': followers_count,
                'following_count': following_count,
                'friends_count': friends_count,
            }
        })
        return data
    
class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id','name','code']
        
class UserLanguageSerializer(serializers.ModelSerializer):
    language = LanguageSerializer()
    
    class Meta:
        model = UserLanguage
        fields = ['id', 'language', 'is_learning', 'proficiency']

        
class UserProfileSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)
    native_languages = serializers.SerializerMethodField()
    learning_languages = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    last_seen_display = serializers.SerializerMethodField()
    date_joined = serializers.SerializerMethodField(source='user.date_joined')
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'unique_id', 'avatar', 'bio', 'native_languages',
            'learning_languages', 'status', 'is_premium', 'xp', 'level', 'streak',
            'total_speak_time', 'total_rooms_joined', 'is_online', 'last_seen', 
            'last_seen_display', 'following', 'followers_count', 'following_count',
            'date_joined'
        ]
    def get_followers_count(self, obj):
        return obj.followers.count()
    
    def get_following_count(self, obj):
        return obj.following.count()
    
    def get_last_seen_display(self, obj):
        if obj.last_seen:
            return timesince(obj.last_seen) + "ago"
        return "Never"
    def get_native_languages(self, obj):
        langs = obj.userlanguage_set.filter(is_learning=False)
        return UserLanguageSerializer(langs, many=True).data

    def get_learning_languages(self, obj):
        langs = obj.userlanguage_set.filter(is_learning=True)
        return UserLanguageSerializer(langs, many=True).data
    
    def get_date_joined(self, obj):
        return obj.user.date_joined if obj.user and hasattr(obj.user, 'date_joined') else None
    
    
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

class PasswordResetOTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, data):
        email = data.get('email')
        code = data.get('code')
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        try:
            otp_obj = OTP.objects.filter(user=user, code=code, is_used=False).latest('created_at')
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")

        if otp_obj.is_expired():
            raise serializers.ValidationError("OTP expired.")

        data['user'] = user
        data['otp_obj'] = otp_obj
        return data

class PasswordResetResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        self.context['user'] = user
        return value
    
    
class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, data):
        email = data.get('email')
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        password = self.validated_data['password']
        user.set_password(password)
        user.save()
        return user


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    native_languages = serializers.ListField(child=serializers.DictField(), required=False)
    learning_languages = serializers.ListField(child=serializers.DictField(), required=False)

    class Meta:
        model = UserProfile
        fields = ['avatar', 'bio', 'native_languages', 'learning_languages']

    def update(self, instance, validated_data):
        print("=== UserProfileUpdateSerializer.update called ===")
        print("Validated data:", validated_data)
        avatar_file = validated_data.pop('avatar', None)
        if avatar_file:
            avatar_url = upload_avatar_to_cloudinary(avatar_file)
            print("Cloudinary returned URL:", avatar_url)
            instance.avatar = avatar_url

        # Update bio
        bio = validated_data.pop('bio', None)
        if bio is not None:
            instance.bio = bio

        # Update native languages
        native_langs = validated_data.pop('native_languages', None)
        if native_langs is not None:
            instance.userlanguage_set.filter(is_learning=False).delete()
            for lang in native_langs:
                UserLanguage.objects.create(
                    user_profile=instance,
                    language_id=lang['language'],
                    is_learning=False,
                    proficiency=lang['proficiency']
                )

        # Update learning languages
        learning_langs = validated_data.pop('learning_languages', None)
        if learning_langs is not None:
            instance.userlanguage_set.filter(is_learning=True).delete()
            for lang in learning_langs:
                UserLanguage.objects.create(
                    user_profile=instance,
                    language_id=lang['language'],
                    is_learning=True,
                    proficiency=lang['proficiency']
                )

        instance.save()
        print("Instance after save. Avatar URL:", instance.avatar)
        return instance



class UserSettingsSerializer(serializers.ModelSerializer):
    language_name = serializers.CharField(source='language.name', read_only=True)
    language_code = serializers.CharField(source='language.code', read_only=True)
    
    class Meta:
        model = UserSettings
        fields = [
            'id',
            'dark_mode',
            'email_notifications', 
            'practice_reminders',
            'room_interest_notifications',
            'browser_notifications',
            'public_profile',
            'show_online_status',
            'language',
            'language_name',
            'language_code',
            'timezone'
        ]
        
    def validate(self, data):
        if not data.get('email_notifications', True):
            data['practice_reminders'] = False
            data['room_interest_notifications'] = False
        return data
    

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)
    
    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
    
    def validate_new_password(self, value):
        try:
            validate_password(value, self.context['request'].user)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("New passwords do not match.")
        
        if data['current_password'] == data['new_password']:
            raise serializers.ValidationError("New password must be different from current password.")
        
        return data
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user