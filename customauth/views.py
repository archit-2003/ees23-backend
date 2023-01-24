from rest_framework import serializers, generics, status, permissions
from rest_framework.response import Response
from .models import UserAcount
from django.core.exceptions import ValidationError
from typing import Tuple
from udyamBackend.settings import CLIENT_ID
import requests
from django.contrib.auth import login, logout
from rest_framework.authtoken.models import Token


GOOGLE_ID_TOKEN_INFO_URL = 'https://oauth2.googleapis.com/tokeninfo'

def google_validate(*, id_token: str, email:str) -> bool:

    response = requests.get(
        GOOGLE_ID_TOKEN_INFO_URL,
        params={'id_token': id_token}
    )

    if not response.ok:
        raise ValidationError('Id token is invalid')

    audience = response.json()['aud']
    if audience != CLIENT_ID:
        raise ValidationError("Invalid Audience")

    if (response.json())["email"]!=email:
        raise ValidationError('Email mismatch')

    return True


def user_create(email, **extra_field) -> UserAcount:
    extra_fields = {
        'is_staff': False,
        'is_active': True,
        **extra_field
    }

    print(extra_fields)

    user = UserAcount(email=email, **extra_fields)
    user.save()
    return user


def user_get_or_create(*, email: str, **extra_data) -> Tuple[UserAcount, bool]:
    user = UserAcount.objects.filter(email=email).first()

    if user:
        return user, False
    return user_create(email=email, **extra_data), True

def user_get_me(*, user: UserAcount):
    token,_ = Token.objects.get_or_create(user = user)
    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'college': user.college_name,
        'year': user.year,
        'phone': user.phone_number,
        'radianite_points': user.radianite_points,
        'referral': user.email[:5]+"#EES-"+str(10000+user.id),
        'token': token.key,
        'message': "Your registration was successfull!",
    }

def user_referred(*, referral):
    if not referral: return
    [verify,id]=referral.split("#EES-")
    user=UserAcount.objects.filter(id=(int(id)-10000))
    if user.count()!=0 and user[0].email[:5]==verify:
        user.update(radianite_points=user[0].radianite_points+5)

class InputSerializer(serializers.Serializer):
        email = serializers.EmailField()
        name = serializers.CharField(required=True)
        college_name = serializers.CharField(required=True)
        year = serializers.CharField(required=True)
        phone_number = serializers.CharField(required=True)

class UserInitApi(generics.GenericAPIView):
    serializer_class=InputSerializer

    def post(self, request, *args, **kwargs):
        id_token = request.headers.get('Authorization')
        email = request.data.get("email")
        google_validate(id_token=id_token,email=email)

        if UserAcount.objects.filter(email=email).count()==0:
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                error = {}
                for err in serializer.errors:
                    error[err] = serializer.errors[err][0]
                return Response(error, status=status.HTTP_409_CONFLICT)
            user_get_or_create(**serializer.validated_data)
            user_referred(referral=request.data.get("referral"))
        
        response = Response(data=user_get_me(user=UserAcount.objects.get(email=email)))
        return response


class LogoutView(generics.GenericAPIView):

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class =  InputSerializer

    def get(self, request):
        request.user.auth_token.delete()
        logout(request)
        return Response(status=status.HTTP_200_OK)

            
