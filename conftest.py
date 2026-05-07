from hypothesis import HealthCheck, settings


settings.register_profile(
    "project_defaults",
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile("project_defaults")
