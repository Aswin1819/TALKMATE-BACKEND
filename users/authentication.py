from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth.models import AnonymousUser

class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that reads tokens from cookies
    """
    
    def authenticate(self, request):
        # First try the default method (Authorization header)
        header_auth = super().authenticate(request)
        if header_auth is not None:
            return header_auth
        
        # If no header auth, try cookie auth
        raw_token = (
            request.COOKIES.get('access_token') or
            request.COOKIES.get('admin_access_token')
        )
        if raw_token is None:
            print(f"No access_token or admin_access_token cookie found. Available cookies: {list(request.COOKIES.keys())}")
            return None
            
        print(f"Found access token in cookie: {raw_token[:20]}...")
            
        try:
            # Validate the token
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            print(f"Cookie auth successful for user: {user}")
            return (user, validated_token)
        except Exception as e:
            print(f"Cookie auth failed: {e}")
            return None
        