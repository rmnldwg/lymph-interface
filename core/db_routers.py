"""
Module for routing database queries to the correct database.
"""

class AccountsRouter:
    """
    Router to control operations on user models in the `accounts` app.
    """
    route_app_labels = [
        "accounts",
        "admin",
        "auth",
        "contenttypes",
        "sessions",
        "messages",
        "staticfiles"
    ]

    def db_for_read(self, model, **hints):
        """
        Suggest database for read operations on models in the `accounts` app.
        """
        if model._meta.app_label in self.route_app_labels:
            return "accounts_db"
        return None

    def db_for_write(self, model, **hints):
        """
        Suggest database for write operations on models in the `accounts` app.
        """
        if model._meta.app_label in self.route_app_labels:
            return "accounts_db"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between Insitutions and Patients.
        """
        if (
            obj1._meta.app_label in self.route_app_labels or
            obj2._meta.app_label in self.route_app_labels
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Allow migrations of models in the matching app.
        """
        if app_label in self.route_app_labels:
            return db == "accounts_db"
        return None
