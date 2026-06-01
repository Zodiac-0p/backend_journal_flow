from django.apps import AppConfig


class JournalsConfig(AppConfig):
    name = 'journals'

    def ready(self):
        import journals.signals  # noqa: F401
