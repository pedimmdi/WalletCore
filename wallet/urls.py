from django.urls import path

from .views import DepositView, WalletView

urlpatterns = [
    path("", WalletView.as_view(), name="wallet"),
    path("deposit/", DepositView.as_view(), name="deposit"),
]