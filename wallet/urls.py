from django.urls import path

from .views import DepositView, WalletView

urlpatterns = [
    path("me/", WalletView.as_view(), name="wallet-me"),
    path("deposit/", DepositView.as_view(), name="deposit"),
]