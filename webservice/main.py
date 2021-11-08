from webservice import views
from flask import Flask

from webservice import config

app = Flask(__name__, instance_relative_config=True)
app.register_blueprint(views.bp)

if __name__ == '__main__':
    app.run(debug=True, host=config.WEBSERVICE_ADDRESS, port=config.WEBSERVICE_PORT)
