from django.urls import path

from .views import (
    GeocodeView,
    PlanCreateView,
    PlanDetailView,
    PlanHeatmapView,
    PurgeExpiredPlansView,
    RiskRulesView,
)

urlpatterns = [
    path("geocode/", GeocodeView.as_view(), name="geocode"),
    path("plans/", PlanCreateView.as_view(), name="plan-create"),
    path("plans/<uuid:plan_id>/", PlanDetailView.as_view(), name="plan-detail"),
    path("plans/<uuid:plan_id>/heatmap/", PlanHeatmapView.as_view(), name="plan-heatmap"),
    path("risk-rules/", RiskRulesView.as_view(), name="risk-rules"),
    path("internal/purge-expired-plans/", PurgeExpiredPlansView.as_view(), name="purge-expired"),
]
