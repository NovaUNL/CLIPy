from CLIPy import CacheStorage, Clip

from . import views, config
from flask import Flask, g, current_app


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    # app.config.from_mapping(
    #     SECRET_KEY='fiambre?queijo!',
    #     DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    # )

    app.config.from_pyfile('config.py', silent=True)

    app.register_blueprint(views.bp)
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
