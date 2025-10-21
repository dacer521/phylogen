from flask import Flask

def create_app(test_config=None):
    """Application factory for the phylogen Flask app."""
    app = Flask(__name__, instance_relative_config=False)

    # Basic configuration
    app.config.from_mapping(
        SECRET_KEY='dev',
    )

    if test_config is not None:
        app.config.update(test_config)

    # Register blueprints or routes
    from . import routes
    app.register_blueprint(routes.bp)

    return app
