from django.urls import path
from .views import WalletView

urlpatterns = [
    path('me/', WalletView.as_view(), name='my-wallet')
]
