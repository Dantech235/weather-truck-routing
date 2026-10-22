from django.urls import path

from .views import GeocodeView, PlanCreateView, PlanDetailView, RiskRulesView

urlpatterns = [
    path("geocode/", GeocodeView.as_view(), name="geocode"),
    path("plans/", PlanCreateView.as_view(), name="plan-create"),
    path("plans/<uuid:plan_id>/", PlanDetailView.as_view(), name="plan-detail"),
    path("risk-rules/", RiskRulesView.as_view(), name="risk-rules"),
]
