from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from urllib.parse import parse_qs


class JWTAuthMiddleware(BaseMiddleware):

    
    def __init__(self, inner):
        super().__init__(inner)
    
    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        
        # Get token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        if token:
            try:
                # Validate JWT token
                # backend include claims in google authentication tokens users
                access_token = AccessToken(token)
                user = await self.get_user_from_token(access_token)
                scope['user'] = user
            except (InvalidToken, TokenError):
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def get_user_from_token(self, access_token):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import AnonymousUser
        
        User = get_user_model()
        try:
            user_id = access_token['user_id']
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()